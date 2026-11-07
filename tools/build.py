#!/usr/bin/env python3
"""Build French v2 using Python 3.9's standard library.

python3 tools/build.py
python3 tools/build.py --from-sqlite
--kaikki, --lexique, --legacy, --db and --output override the default paths.
SQLite is the translation source of truth. A source rebuild preserves existing v2
translations as well as importing v1 lines into the first sense. Split index values
list the child shard keys replacing a parent key; short words
are padded with underscores. Shard keys deliberately retain v1's œ -> _ behavior.
"""
import argparse
import csv
import copy
import gzip
import json
import os
import re
import sqlite3
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path.home() / 'git/zabankhan-dict-src'
LEGACY = Path('/Users/ziaee/git/zabankhan/content-tools/out/fr-dict.sqlite')
POS = {'noun': 'noun', 'verb': 'verb', 'adj': 'adjective', 'adv': 'adverb',
       'pron': 'pronoun', 'prep': 'preposition', 'conj': 'conjunction',
       'intj': 'interjection', 'det': 'article', 'article': 'article',
       'num': 'numeral', 'phrase': 'phrase', 'prep_phrase': 'phrase',
       'particle': 'particle', 'prefix': 'prefix', 'suffix': 'suffix', 'abbrev': 'abbreviation'}
TAGS = set('informal formal slang figurative dated rare vulgar derogatory transitive intransitive pronominal uncountable plural-only Quebec Belgium Switzerland'.split())
TAG_ALIASES = {'reflexive': 'pronominal', 'pluralia-tantum': 'plural-only', 'Québec': 'Quebec'}
TENSES = [({'indicative', 'present'}, 'present'), ({'indicative', 'imperfect'}, 'imperfect'),
          ({'indicative', 'future'}, 'future'), ({'conditional'}, 'conditional'),
          ({'subjunctive', 'present'}, 'subjunctive'), ({'past', 'participle'}, 'past_participle'),
          ({'present', 'participle'}, 'present_participle')]
PERSONS = [(set((p, n)), i) for i, (p, n) in enumerate(
    [(p, n) for n in ('singular', 'plural') for p in ('first-person', 'second-person', 'third-person')])]
SOURCES = 'English Wiktionary via kaikki.org (CC BY-SA 4.0); Lexique 3.83 (CC BY-SA 4.0); French Wiktionary (CC BY-SA 4.0)'


def clean(value):
    return ' '.join(str(value).split()).replace('’', "'")


def normalize(word):
    return unicodedata.normalize('NFC', clean(word)).lower()


def shard_key(word, width=2):
    first = normalize(word).split()[0] if normalize(word) else ''
    letters = ''.join(c for c in unicodedata.normalize('NFD', first) if not unicodedata.combining(c))
    return ''.join(c if 'a' <= c <= 'z' else '_' for c in letters[:width]).ljust(width, '_')


def lookup_shard_key(word, index):
    """Return the shard key using index.split, including padded short words."""
    key = shard_key(word)
    while key in index.get('split', {}):
        key = shard_key(word, len(key) + 1)
    return key


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def frequencies(path):
    result = defaultdict(float)
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row['islem'] == '1':
                try:
                    word = normalize(row['lemme'])
                    result[word] = max(result[word], float(row['freqlemfilms2'] or 0) + float(row['freqlemlivres'] or 0))
                except ValueError:
                    pass
    return result


def form_frequencies(rows):
    result = defaultdict(float)
    for row in rows:
        try: result[normalize(row['ortho'])] = max(result[normalize(row['ortho'])], float(row['freqfilms2'] or 0), float(row['freqlivres'] or 0))
        except (ValueError, KeyError): pass
    return result


def lexique_rows(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f, delimiter='\t')


def lex_pos(code):
    if code.startswith('PRO'): return 'pronoun'
    if code.startswith('ART'): return 'article'
    if code == 'ADJ:num': return 'numeral'
    if code.startswith('ADJ:'): return 'determiner'
    return {'NOM':'noun','VER':'verb','AUX':'verb','ADJ':'adjective','ADV':'adverb',
            'PRE':'preposition','CON':'conjunction','ONO':'interjection'}.get(code)


def lex_form_label(row):
    tags = set()
    genre, nombre, info = row.get('genre',''), row.get('nombre',''), row.get('infover','')
    if genre in ('m','f'): tags.add(genre)
    if nombre in ('s','p'): tags.add('singular' if nombre == 's' else 'plural')
    info = info.lower()
    codes = {'inf':'infinitive','par:pas':'past.participle','par:pre':'present.participle',
             'ind:pre':'indicative.present','ind:imp':'indicative.imperfect','ind:fut':'indicative.future',
             'cnd:pre':'conditional','sub:pre':'subjunctive.present','sub:imp':'subjunctive.imperfect',
             'imp:pre':'imperative'}
    parts = set()
    for item in info.strip(';').split(';'):
        bits = item.split(':')
        if len(bits) >= 2:
            tense = codes.get(':'.join(bits[:2]))
            if tense: parts.update(tense.split('.'))
            if len(bits) == 3 and bits[2][-1:] in ('s','p'):
                person = bits[2][0]
                tags.add(('first-person','second-person','third-person')[int(person)-1])
                tags.add('singular' if bits[2][-1]=='s' else 'plural')
    tags.update(parts)
    return form_label(tags)


def band(freq):
    # Combined film/book occurrences per million; zero means absent from Lexique.
    return 5 if freq >= 100 else 4 if freq >= 20 else 3 if freq >= 5 else 2 if freq >= 1 else 1


def gender(raw):
    for template in raw.get('head_templates', []):
        args = template.get('args', {})
        value = args.get('g') or args.get('1', '')
        if value.split('-')[0] in ('m', 'f', 'mf'):
            return value.split('-')[0]
    return ''


def usable_forms(raw):
    for form in raw.get('forms', []):
        tags = set(form.get('tags', []))
        word = clean(form.get('form', ''))
        if word and not tags & {'multiword-construction', 'table-tags', 'inflection-template'}:
            yield word, tags


def forms(raw, pos, word):
    result = {'infinitive': word} if pos == 'verb' else {'masculine': word} if pos == 'adjective' else {}
    if pos == 'verb':
        for form in raw.get('forms', []):
            if 'infinitive' in form.get('tags', []) and 'multiword-construction' in form.get('tags', []):
                match = re.search(r'(avoir|être) \+ ', form.get('form', ''))
                if match:
                    result.setdefault('auxiliary', match.group(1))
    for value, tags in usable_forms(raw):
        if pos == 'verb':
            if 'auxiliary' in tags:
                result.setdefault('auxiliary', value)
            for required, name in TENSES:
                if required <= tags:
                    if name.endswith('participle'):
                        if not tags & {'feminine', 'plural'}:
                            result.setdefault(name, value)
                    else:
                        for required_person, index in PERSONS:
                            if required_person <= tags:
                                result.setdefault(name, [''] * 6)
                                if not result[name][index]:
                                    result[name][index] = value
                    break
        elif pos == 'adjective':
            name = ('feminine' if 'feminine' in tags else 'masculine') + ('_plural' if 'plural' in tags else '')
            if tags & {'feminine', 'masculine', 'plural'}:
                result.setdefault(name, value)
        elif pos == 'noun':
            if 'plural' in tags:
                result.setdefault('plural', value)
            elif 'feminine' in tags:
                result.setdefault('feminine', value)
    return result


def form_label(tags):
    codes = [('indicative', 'ind'), ('subjunctive', 'subj'), ('conditional', 'cond'),
             ('imperative', 'imp'), ('present', 'pres'), ('imperfect', 'impf'),
             ('future', 'fut'), ('past', 'past'), ('infinitive', 'inf'),
             ('masculine', 'm'), ('feminine', 'f')]
    if {'past', 'participle'} <= tags:
        parts = ['pp']
    elif {'present', 'participle'} <= tags:
        parts = ['ppr']
    else:
        parts = [code for tag, code in codes[:9] if tag in tags]
    parts += [code for tag, code in codes[9:] if tag in tags]
    person = next((str(i) for i, tag in enumerate(
        ('first-person', 'second-person', 'third-person'), 1) if tag in tags), '')
    number = 's' if 'singular' in tags else 'p' if 'plural' in tags else ''
    if person:
        parts.append(person + number)
    elif number:
        parts.append('sg' if number == 's' else 'pl')
    return '.'.join(parts) or ('refl' if 'pronominal' in tags else 'form')


def merge_labels(labels):
    groups = defaultdict(set)
    for label in labels:
        prefix, _, person = label.rpartition('.')
        if re.fullmatch(r'[123][sp]?', person):
            groups[prefix].add(person)
        else:
            groups[label]
    return ';'.join(prefix + ('.' + ','.join(sorted(persons)) if persons else '')
                    for prefix, persons in sorted(groups.items()))


def bare_reflexive(word, pos):
    base = re.sub(r"^(?:se |s')", '', normalize(word))
    return pos == 'verb' and base != normalize(word) and not re.search(r"[\s']", base)


def redirect_allowed(source, target, pos):
    # Apostrophes also mark multiword elisions, except for a bare reflexive.
    return (bool(re.search(r"[\s']", normalize(source))) or
            not re.search(r"[\s']", normalize(target)) or bare_reflexive(target, pos))


def read_translations(path):
    senses, examples = {}, {}
    if Path(path).exists():
        with sqlite3.connect('file:' + str(Path(path).resolve()) + '?mode=ro', uri=True) as db:
            senses = {(w, p, en): fa for w, p, en, fa in db.execute(
                "SELECT e.word,e.pos,s.en,s.fa FROM sense s JOIN entry e ON e.id=s.entry_id WHERE s.fa!=''")}
            examples = {(w, p, en, text): fa for w, p, en, text, fa in db.execute(
                "SELECT e.word,e.pos,s.en,x.text,x.fa FROM example x JOIN sense s ON s.id=x.sense_id JOIN entry e ON e.id=s.entry_id WHERE x.fa!=''")}
    return senses, examples


def build_database(kaikki, lexique, destination, legacy=LEGACY):
    destination = Path(destination)
    previous_senses, previous_examples = read_translations(destination)
    old = {}
    if legacy and Path(legacy).exists():
        with sqlite3.connect('file:' + str(Path(legacy).resolve()) + '?mode=ro', uri=True) as db:
            old = {(clean(w), p): fa for w, p, fa in db.execute("SELECT word,pos,fa FROM entry WHERE fa!=''")}
    freq = frequencies(lexique)
    lex_rows = list(lexique_rows(lexique)) if 'ortho' in (next(iter(lexique_rows(lexique)), {}) or {}) else []
    form_freq = form_frequencies(lex_rows)
    entries, edges = {}, defaultdict(lambda: defaultdict(set))

    def redirect(source, target, pos, label):
        if normalize(source) != normalize(target) and redirect_allowed(source, target, pos):
            edges[(normalize(source), pos)][clean(target)].add(frozenset(label) if not isinstance(label, str) else frozenset({'pronominal'}))

    with gzip.open(kaikki, 'rt', encoding='utf-8') as f:
        for line in f:
            raw = json.loads(line)
            word, pos = clean(raw.get('word', '')), POS.get(raw.get('pos'))
            if not word or not pos or raw.get('lang_code', 'fr') != 'fr':
                continue
            senses = []
            for sense in raw.get('senses', []):
                targets = sense.get('form_of', []) + sense.get('alt_of', [])
                if targets or set(sense.get('tags', [])) & {'form-of', 'alt-of'}:
                    for target in targets:
                        redirect(word, target['word'], pos, set(sense.get('tags', [])))
                    continue
                glosses = [clean(g) for g in sense.get('glosses', []) if clean(g)]
                if not glosses:
                    continue
                tags = [TAG_ALIASES.get(t, t) for t in sense.get('tags', []) + sense.get('raw_tags', [])]
                senses.append({'en': '; '.join(glosses), 'fa': '', 'tags': list(dict.fromkeys(t for t in tags if t in TAGS)),
                               'examples': [{'text': clean(x['text']), 'en': clean(x.get('english') or x.get('translation', '')), 'fa': ''}
                                            for x in sense.get('examples', []) if x.get('text')][:2],
                               'synonyms': list(dict.fromkeys(clean(x['word']) for x in sense.get('synonyms', []) if x.get('word')))})
            for value, tags in usable_forms(raw):
                redirect(value, word, pos, tags)
            if not senses:
                continue
            key = (word, pos)
            if key not in entries:
                entries[key] = {'word': word, 'pos': pos, 'freq': band(freq[normalize(word)]) if normalize(word) in freq else 0,
                                'ipa': next((s['ipa'] for s in raw.get('sounds', []) if s.get('ipa')), ''),
                                'gender': gender(raw),
                                'audio': next((s.get('mp3_url') or s.get('ogg_url') for s in raw.get('sounds', []) if s.get('mp3_url') or s.get('ogg_url')), ''),
                                'senses': [], 'forms': {}, 'expressions': [], 'more_examples': []}
            e = entries[key]
            e['forms'].update({k: v for k, v in forms(raw, pos, word).items() if k not in e['forms']})
            for sense in senses:
                if len(e['senses']) < 8 and sense not in e['senses']:
                    e['senses'].append(sense)

    # Entry-level examples are candidates only when every sense lacks examples.
    candidates = defaultdict(set)
    example_source = Path(kaikki).parent/'frwiktionary-fr.jsonl.gz'
    if example_source.exists():
        with gzip.open(example_source, 'rt', encoding='utf-8') as source:
            for line in source:
                raw = json.loads(line)
                if raw.get('lang_code','fr') != 'fr': continue
                key = (normalize(clean(raw.get('word',''))), POS.get(raw.get('pos')))
                if key not in entries: continue
                for sense in raw.get('senses', []):
                    for example in sense.get('examples', []):
                        text = clean(example.get('text',''))
                        if (20 <= len(text) <= 160 and not re.search(r'[\[\]{}]', text)
                                and not re.search(r'(?:^|\s)(?:source|référence|ref\.)\s*:', text, re.I)):
                            candidates[key].add(text)
    for key, e in entries.items():
        if e['senses'] and not any(s['examples'] for s in e['senses']):
            e['more_examples'] = sorted(candidates[key], key=lambda x:(len(x),x))[:3]

    # Add frequent Lexique inflections when the lemma+POS exists locally.
    headwords = {(normalize(w), p): w for w, p in entries}
    for row in lex_rows:
        word, lemma, pos = normalize(row['ortho']), normalize(row['lemme']), lex_pos(row['cgram'])
        try: row_freq = max(float(row.get('freqfilms2') or 0), float(row.get('freqlivres') or 0))
        except ValueError: row_freq = 0
        lemma = lemma.replace('oe', 'œ') if (lemma.replace('oe', 'œ'), pos) in headwords or any(h == lemma.replace('oe', 'œ') for h, _ in headwords) else lemma
        if pos and word != lemma and row_freq > 1:
            # Lexique and Wiktionary label determiners differently (adjective vs article/pronoun); fall back to any POS of the lemma.
            target = (lemma, pos) if (lemma, pos) in headwords else next(((h, p) for h, p in headwords if h == lemma), None)
            if target:
                edges[(word, target[1])][headwords[target]].add(frozenset({lex_form_label(row)}))

    # Lexique redirects from a frequent headword with unattested POS are likely noise.
    lex_attested = {(normalize(r['ortho']), lex_pos(r['cgram'])) for r in lex_rows if lex_pos(r['cgram'])}
    dropped = []
    headword_words = {h for h, _ in headwords}
    for source, pos in list(edges):
        if form_freq.get(source, 0) > 10 and (source, pos) not in lex_attested and source in headword_words:
            dropped.append((source, pos, '; '.join(sorted(edges[(source,pos)]))))
            del edges[(source,pos)]
    drop_path = ROOT/'validation/dropped-redirects.csv'
    drop_path.parent.mkdir(parents=True, exist_ok=True)
    with drop_path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.writer(f); writer.writerow(['form','pos','targets']); writer.writerows(sorted(dropped))

    # Wiktionary also puts reflexive senses under the bare infinitive.
    for (word, pos), e in list(entries.items()):
        reflexive = [s for s in e['senses'] if 'pronominal' in s['tags']]
        if pos == 'verb' and reflexive and not re.match(r"^(?:se |s')", word):
            reflexive_word = ("s'" if word[0].lower() in 'aeiouyàâéèêëîïôùûüœ' else 'se ') + word
            if (reflexive_word, pos) not in entries:
                variant = copy.deepcopy(e)
                variant.update(word=reflexive_word, senses=copy.deepcopy(reflexive), forms={'infinitive': reflexive_word})
                entries[(reflexive_word, pos)] = variant

    by_word = defaultdict(list)
    canonical = {}
    for (word, pos), e in entries.items():
        by_word[normalize(word)].append(e)
        canonical.setdefault((normalize(word), pos), word)
        for i, sense in enumerate(e['senses']):
            sense['fa'] = previous_senses.get((word, pos, sense['en']), old.get((word, pos), '') if i == 0 else '')
            for example in sense['examples']:
                example['fa'] = previous_examples.get((word, pos, sense['en'], example['text']), '')
        base = re.sub(r"^(?:se |s')", '', word)
        if base and base != word:
            redirect(base, word, pos, 'pronominal')

    # Expressions are linked in a second pass so source ordering cannot hide a parent.
    for e in entries.values():
        if ' ' in e['word']:
            base = re.sub(r"^(?:se |s')", '', e['word'])
            for token in set(re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", normalize(base))):
                for parent in by_word.get(token, []):
                    parent['expressions'].append(e['word'])
    def expression_rank(word):
        words = re.findall(r"[^\W\d_]+", normalize(word))
        offensive = any({'vulgar', 'derogatory'} & set(s['tags'])
                        for e in by_word[normalize(word)] for s in e['senses'])
        return (offensive, len(words), -min((freq.get(w, 0) for w in words), default=0), word)

    for e in entries.values():
        e['expressions'] = sorted(set(e['expressions']), key=expression_rank)[:30]

    # Resolve form-of chains with POS intact, retaining all ambiguous targets.
    def resolve(source, pos):
        found = defaultdict(set)
        stack = [(target, tags, frozenset({source}))
                 for target, labels in edges[(source, pos)].items() for tags in labels]
        while stack:
            target, labels, seen = stack.pop()
            normalized = normalize(target)
            key = (normalized, pos)
            if key in canonical:
                if redirect_allowed(source, canonical[key], pos):
                    found[canonical[key]].add(form_label(labels))
            if normalized not in seen:
                for next_target, next_labels in edges.get(key, {}).items():
                    for tags in next_labels:
                        stack.append((next_target, labels | tags, seen | {normalized}))
        return found

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.building.sqlite')
    if temporary.exists():
        temporary.unlink()
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript('''
                PRAGMA foreign_keys=ON;
                CREATE TABLE entry(id INTEGER PRIMARY KEY, word TEXT NOT NULL, pos TEXT NOT NULL, freq INTEGER NOT NULL,
                    frequency REAL NOT NULL, ipa TEXT NOT NULL, gender TEXT NOT NULL, audio TEXT NOT NULL,
                    forms TEXT NOT NULL, expressions TEXT NOT NULL, UNIQUE(word,pos));
                CREATE TABLE sense(id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES entry(id),
                    position INTEGER NOT NULL, en TEXT NOT NULL, fa TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL, synonyms TEXT NOT NULL);
                CREATE TABLE example(id INTEGER PRIMARY KEY, sense_id INTEGER NOT NULL REFERENCES sense(id),
                    position INTEGER NOT NULL, text TEXT NOT NULL, en TEXT NOT NULL, fa TEXT NOT NULL DEFAULT '');
                CREATE TABLE redirect(word TEXT NOT NULL, lemma TEXT NOT NULL, pos TEXT NOT NULL, form TEXT NOT NULL,
                    PRIMARY KEY(word,lemma,pos));
                CREATE INDEX entry_word ON entry(word);
                CREATE INDEX sense_entry ON sense(entry_id);
                CREATE INDEX example_sense ON example(sense_id);
                CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
            more_examples = {}
            entry_ids_written = {}
            for e in sorted(entries.values(), key=lambda e: (-freq.get(normalize(e['word']), -1), e['word'], e['pos'])):
                eid = db.execute('INSERT INTO entry(word,pos,freq,frequency,ipa,gender,audio,forms,expressions) VALUES(?,?,?,?,?,?,?,?,?)',
                                 (e['word'], e['pos'], e['freq'], freq.get(normalize(e['word']), 0), e['ipa'], e['gender'], e['audio'], dumps(e['forms']), dumps(e['expressions']))).lastrowid
                if e.get('more_examples'): more_examples[str(eid)] = e['more_examples']
                entry_ids_written[(e['word'],e['pos'])] = eid
                for i, s in enumerate(e['senses']):
                    sid = db.execute('INSERT INTO sense(entry_id,position,en,fa,tags,synonyms) VALUES(?,?,?,?,?,?)',
                                     (eid, i, s['en'], s['fa'], dumps(s['tags']), dumps(s['synonyms']))).lastrowid
                    for j, x in enumerate(s['examples']):
                        db.execute('INSERT INTO example(sense_id,position,text,en,fa) VALUES(?,?,?,?,?)', (sid, j, x['text'], x['en'], x['fa']))
            db.executemany('INSERT INTO meta VALUES(?,?)', [('lang', 'fr'), ('format', '2'), ('sources', SOURCES), ('more_examples', dumps(more_examples))])
            for source, pos in list(edges):
                for target, labels in resolve(source, pos).items():
                    if source != normalize(target):
                        db.execute('INSERT INTO redirect VALUES(?,?,?,?)', (source, target, pos, merge_labels(labels)))
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def export_shards(database, output, max_bytes=999_999):
    output = Path(output)
    shards = defaultdict(lambda: {'entries': [], 'redirects': {}})
    audio_prefixes = []
    audio_prefix_ids = {}
    with sqlite3.connect('file:' + str(Path(database).resolve()) + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        examples = defaultdict(list)
        for row in db.execute('SELECT * FROM example ORDER BY sense_id,position'):
            examples[row['sense_id']].append({k: row[k] for k in ('text', 'en', 'fa')})
        senses = defaultdict(list)
        for row in db.execute('SELECT * FROM sense ORDER BY entry_id,position'):
            senses[row['entry_id']].append({'en': row['en'], 'fa': row['fa'], 'tags': json.loads(row['tags']),
                                           'synonyms': json.loads(row['synonyms']), 'examples': examples[row['id']]})
        more_row = db.execute("SELECT value FROM meta WHERE key='more_examples'").fetchone()
        more_examples = json.loads(more_row[0]) if more_row else {}
        entry_ids = {}
        for row in db.execute('SELECT * FROM entry ORDER BY id'):
            e = {k: row[k] for k in ('id', 'word', 'pos', 'freq', 'ipa', 'gender', 'audio')}
            e.update(senses=senses[row['id']], forms=json.loads(row['forms']), expressions=json.loads(row['expressions']))
            if more_examples.get(str(row['id'])): e['more_examples'] = more_examples[str(row['id'])]
            entry_ids[(e['word'], e['pos'])] = e['id']
            if e['audio'].startswith(('https://', 'http://')) and len(e['audio'].split('/', 3)) == 4:
                parts = e['audio'].split('/', 3)
                prefix, filename = e['audio'].rsplit('/', 1)
                prefix += '/'
                if prefix not in audio_prefix_ids:
                    audio_prefix_ids[prefix] = len(audio_prefixes)
                    audio_prefixes.append(prefix)
                e['audio'] = [audio_prefix_ids[prefix], filename]
            e = {k: v for k, v in e.items() if v not in ('', [], {})}
            for sense in e.get('senses', []):
                for example in sense.get('examples', []):
                    for key in list(example):
                        if example[key] == '':
                            del example[key]
                for key in list(sense):
                    if sense[key] in ('', []):
                        del sense[key]
            shards[shard_key(e['word'])]['entries'].append(e)
        for row in db.execute('SELECT * FROM redirect ORDER BY word,lemma,pos'):
            shards[shard_key(row['word'])]['redirects'].setdefault(row['word'], []).append([entry_ids[(row['lemma'], row['pos'])], row['form']])
        counts = {table: db.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in ('entry', 'sense', 'example', 'redirect')}
        persian = db.execute("SELECT count(DISTINCT entry_id) FROM sense WHERE fa!=''").fetchone()[0]
        sources = db.execute("SELECT value FROM meta WHERE key='sources'").fetchone()[0]
    targets = {eid: [word, pos] for (word, pos), eid in entry_ids.items()}

    def encode_shard(shard):
        ids = {redirect[0] for redirects in shard['redirects'].values() for redirect in redirects}
        wire = dict(shard, targets={eid: targets[eid] for eid in sorted(ids)})
        wire['entries'] = [dict(e, senses=[
            [s.get('en', ''), s.get('fa', ''), s.get('tags', []), s.get('synonyms', []),
             [[x.get('text', ''), x.get('en', ''), x.get('fa', '')] for x in s.get('examples', [])]]
            for s in e.get('senses', [])]) for e in shard['entries']]
        fields = ('id', 'word', 'pos', 'freq', 'ipa', 'gender', 'audio', 'senses', 'forms', 'expressions', 'more_examples')
        wire['entries'] = [[e.get(k, [] if k in ('senses', 'expressions') else {} if k == 'forms' else '')
                            for k in fields] for e in wire['entries']]
        labels = sorted({r[1] for redirects in shard['redirects'].values() for r in redirects})
        label_ids = {label: i for i, label in enumerate(labels)}
        wire['form_labels'] = labels
        wire['redirects'] = {word: [[r[0], label_ids[r[1]]] for r in redirects]
                             for word, redirects in shard['redirects'].items()}
        return dumps(wire).encode('utf-8')

    split = {}
    pending = list(shards)
    while pending:
        key = pending.pop()
        if len(encode_shard(shards[key])) <= max_bytes:
            continue
        shard = shards[key]
        children = set()
        width = len(key) + 1
        for entry in shard['entries']:
            children.add(shard_key(entry['word'], width))
        for word in shard['redirects']:
            children.add(shard_key(word, width))
        # Tiny test limits may be smaller than one indivisible entry.
        if len(children) == 1 and width > max(
                [len(normalize(e['word']).split()[0]) for e in shard['entries']] +
                [len(normalize(w).split()[0]) for w in shard['redirects']] + [0]):
            if max_bytes == 999_999:
                raise ValueError('Indivisible shard exceeds size limit: ' + key)
            continue
        shards.pop(key)
        for entry in shard['entries']:
            shards[shard_key(entry['word'], width)]['entries'].append(entry)
        for word, redirects in shard['redirects'].items():
            shards[shard_key(word, width)]['redirects'][word] = redirects
        split[key] = sorted(children)
        pending.extend(children)
    encoded = {key: encode_shard(value) for key, value in sorted(shards.items())}
    # Do not silently publish an oversized three-letter shard.
    oversized = {key: len(value) for key, value in encoded.items() if len(value) > max_bytes}
    if oversized and max_bytes == 999_999:
        raise ValueError('Shards exceed size limit: ' + str(oversized))
    index = {'lang': 'fr', 'format': 2, 'version': int(time.time()), 'entries': counts['entry'],
             'persian': persian, 'shards': sorted(shards), 'sources': sources, 'split': split, 'audio_prefixes': audio_prefixes}
    output.mkdir(parents=True, exist_ok=True)
    for key, content in encoded.items():
        path = output / (key + '.json')
        tmp = path.with_suffix('.json.tmp')
        tmp.write_bytes(content)
        os.replace(tmp, path)
    tmp = output / 'index.json.tmp'
    tmp.write_text(dumps(index), encoding='utf-8')
    os.replace(tmp, output / 'index.json')
    for path in output.glob('*.json'):
        if path.stem != 'index' and path.stem not in shards:
            path.unlink()
    sizes = [len(value) for value in encoded.values()]
    print('entries={entry:,} senses={sense:,} examples={example:,} redirects={redirect:,}'.format(**counts))
    print('persian={} shards={} max={:,} bytes total={:,} bytes split={}'.format(persian, len(sizes), max(sizes, default=0), sum(sizes), dumps(split)), flush=True)
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kaikki', type=Path, default=SOURCE / 'kaikki.org-dictionary-French.jsonl.gz')
    parser.add_argument('--lexique', type=Path, default=SOURCE / 'Lexique383.tsv')
    parser.add_argument('--legacy', type=Path, default=LEGACY)
    parser.add_argument('--db', type=Path, default=ROOT / 'dist/fr-v2.sqlite')
    parser.add_argument('--output', type=Path, default=ROOT / 'fr/v2')
    parser.add_argument('--from-sqlite', action='store_true')
    args = parser.parse_args()
    if not args.from_sqlite:
        build_database(args.kaikki, args.lexique, args.db, args.legacy)
    export_shards(args.db, args.output)


if __name__ == '__main__':
    main()
