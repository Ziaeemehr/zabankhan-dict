#!/usr/bin/env python3
"""Import checked per-sense Persian meanings: WORK.sqlite PACK.sqlite."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import unicodedata

SOURCE = ('gpt-6-luna generated per sense, automatically checked (not human-reviewed); '
          'prompt sense-fa-v1')


def normalize(gloss):
    gloss = ' '.join(gloss.lower().split())
    while gloss and unicodedata.category(gloss[-1]).startswith('P'):
        gloss = gloss[:-1].rstrip()
    return gloss


def import_senses(work, pack):
    by_gloss = defaultdict(list)
    by_position = defaultdict(list)
    for sid, word, pos, position, en in pack.execute(
            'SELECT s.id,e.word,e.pos,s.position,s.en FROM sense s '
            'JOIN entry e ON e.id=s.entry_id'):
        gloss = normalize(en)
        by_gloss[word, pos, gloss].append(sid)
        by_position[word, pos, position].append((sid, gloss))
    counts = dict(passed=0, matched=0, filled=0, skipped=0)
    examples = []
    before = pack.execute("SELECT count(*) FROM sense WHERE trim(coalesce(fa,''))!=''").fetchone()[0]
    with pack:
        for word, pos, en, position, fa in work.execute(
                'SELECT e.word,e.pos,e.en,f.sense,f.fa FROM sense_fa f '
                "JOIN entry e ON e.id=f.entry_id WHERE f.status='passed' "
                'ORDER BY f.entry_id,f.sense'):
            counts['passed'] += 1
            glosses = json.loads(en)
            gloss = normalize(glosses[position]) if 0 <= position < len(glosses) else ''
            candidates = by_gloss.get((word, pos, gloss), []) if gloss else []
            sid = candidates[0] if len(candidates) == 1 else None
            if sid is None and gloss:
                fallback = [s for s, g in by_position.get((word, pos, position), []) if g == gloss]
                if len(fallback) == 1:
                    sid = fallback[0]
            if sid is not None:
                counts['matched'] += 1
            if sid is not None and fa and fa.strip():
                changed = pack.execute(
                    "UPDATE sense SET fa=? WHERE id=? AND trim(coalesce(fa,''))=''",
                    (fa, sid)).rowcount
            else:
                changed = 0
            counts['filled'] += changed
            if not changed:
                counts['skipped'] += 1
                if len(examples) < 10:
                    reason = 'unmatched/ambiguous gloss' if sid is None else 'existing or empty Persian'
                    examples.append((word, pos, position, gloss, reason))
        pack.execute('INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)', ('fa_source', SOURCE))
    after = pack.execute("SELECT count(*) FROM sense WHERE trim(coalesce(fa,''))!=''").fetchone()[0]
    for key, value in counts.items():
        print(f'{key}: {value}')
    for example in examples:
        print('skipped example:', json.dumps(example, ensure_ascii=False))
    print(f'pack senses with fa before: {before}; after: {after}')
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    parser.add_argument('pack', type=Path)
    args = parser.parse_args()
    if args.work.resolve() == args.pack.resolve():
        parser.error('work and pack must be different files')
    with sqlite3.connect(args.work.resolve().as_uri() + '?mode=ro', uri=True) as work:
        with sqlite3.connect(args.pack.resolve().as_uri() + '?mode=rw', uri=True) as pack:
            import_senses(work, pack)


if __name__ == '__main__':
    main()
