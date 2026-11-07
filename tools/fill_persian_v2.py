#!/usr/bin/env python3
"""Fill missing v2 sense/example Persian using the local OpenAI-compatible server.

python3 tools/fill_persian_v2.py [dist/fr-v2.sqlite] --limit 20000
Each batch is committed; rerunning selects only missing translations, ordered by
Lexique frequency. Ctrl-C stops cleanly. No API key or external service is used.
"""
import argparse
import json
import re
import signal
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

PROMPT = '''You are a French-Persian lexicographer writing a learner's dictionary.
For each item below give its Persian translation:
- For a sense: 1 to 4 Persian equivalents, separated by "، ". Translate only that English sense.
- Verbs as Persian infinitives (e.g. رفتن). Nouns and adjectives without articles.
- For an example: translate the complete French sentence naturally, following its sense and English translation.
- No transliteration, no French, no notes. Follow the part of speech and English gloss.
Answer with JSON only: {"<id>": "<Persian translation>", ...} with every id below.

'''
PERSIAN = re.compile(r'[\u0600-\u06ff]')


def ask(url, model, items):
    request = urllib.request.Request(url.rstrip('/') + '/v1/chat/completions',
        data=json.dumps({'model': model, 'temperature': 0.2, 'response_format': {'type': 'json_object'},
                         'messages': [{'role': 'user', 'content': PROMPT + '\n'.join(json.dumps(i, ensure_ascii=False) for i in items)}]}).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=600) as response:
        content = json.load(response)['choices'][0]['message']['content']
    answer = json.loads(content[content.find('{'):content.rfind('}') + 1])
    if not isinstance(answer, dict):
        raise ValueError('Expected a JSON object')
    return answer


def pending(db, limit):
    # Sense/example ids have separate namespaces. Order both together by frequency.
    rows = db.execute('''
        SELECT * FROM (
        SELECT 'sense' kind,s.id,e.word,e.pos,e.gender,s.en gloss,'' text,'' english,
               e.frequency,e.freq,e.id entry_id,s.position,0 example_position
        FROM sense s JOIN entry e ON e.id=s.entry_id WHERE s.fa=''
        UNION ALL
        SELECT 'example',x.id,e.word,e.pos,e.gender,s.en,x.text,x.en,
               e.frequency,e.freq,e.id,s.position,x.position+1
        FROM example x JOIN sense s ON s.id=x.sense_id JOIN entry e ON e.id=s.entry_id WHERE x.fa=''
        ) ORDER BY frequency DESC,freq DESC,entry_id,position,example_position,kind,id LIMIT ?
    ''', (limit,)).fetchall()
    return [{'id': ('s' if r[0] == 'sense' else 'x') + str(r[1]), 'kind': r[0], 'word': r[2],
             'pos': r[3], 'gender': r[4], 'en': r[5],
             **({'text': r[6], 'english': r[7]} if r[0] == 'example' else {})} for r in rows]


def apply_answers(db, items, answers):
    allowed = {item['id']: item for item in items}
    done = 0
    for key, value in answers.items():
        if key not in allowed or not isinstance(value, str):
            continue
        value = value.strip()
        item = allowed[key]
        if not value or not PERSIAN.search(value) or re.search(r'[A-Za-z]', value):
            continue
        if len(value) > (3000 if item['kind'] == 'example' else 240):
            continue
        table = 'sense' if item['kind'] == 'sense' else 'example'
        done += db.execute('UPDATE ' + table + " SET fa=? WHERE id=? AND fa=''", (value, int(key[1:]))).rowcount
    db.commit()
    return done


def fill(db, url, model, limit, batch_size, minutes=None):
    items = pending(db, limit)
    print('{} missing translations selected'.format(len(items)), flush=True)
    start, done, failed = time.monotonic(), 0, 0
    for offset in range(0, len(items), batch_size):
        if minutes is not None and time.monotonic() - start >= minutes * 60:
            break
        chunk = items[offset:offset + batch_size]
        answers = {}
        for attempt in range(3):
            try:
                answers = ask(url, model, chunk)
                break
            except (OSError, ValueError, KeyError, IndexError) as error:
                print('batch {} attempt {}: {}'.format(offset, attempt + 1, error), file=sys.stderr, flush=True)
                if attempt == 2:
                    failed += 1
        done += apply_answers(db, chunk, answers)
        print('{}/{} processed; {} filled ({:.1f}/s)'.format(min(offset + batch_size, len(items)), len(items), done,
                                                           done / max(1, time.monotonic() - start)), flush=True)
    return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('db', nargs='?', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/fr-v2.sqlite')
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    parser.add_argument('--model', default='gemma4')
    parser.add_argument('--limit', type=int, default=20000, help='maximum missing senses and examples to process')
    parser.add_argument('--batch-size', type=int, default=20)
    parser.add_argument('--minutes', type=float)
    args = parser.parse_args()
    if args.limit < 0 or args.batch_size < 1 or (args.minutes is not None and args.minutes <= 0):
        parser.error('limit must be nonnegative; batch-size and minutes must be positive')
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    with sqlite3.connect('file:' + str(args.db.resolve()) + '?mode=rw', uri=True) as db:
        try:
            failed = fill(db, args.url, args.model, args.limit, args.batch_size, args.minutes)
        except KeyboardInterrupt:
            print('Stopped; completed batches are saved.', flush=True)
            return 0
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
