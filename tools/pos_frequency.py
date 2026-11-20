#!/usr/bin/env python3
"""Give each (word, part of speech) entry its own Lexique frequency.

Lexique lists frequency per lemma and grammatical category: "pendant" is 763/million
as a preposition but 4 as a noun. Without this, every homograph got the word's
largest value, so the app could not tell which part of speech to show first.

python3 tools/pos_frequency.py [dist/fr-v2.sqlite] [--lexique Lexique383.tsv]
build.py calls apply_pos_frequencies() too, so a full rebuild keeps this.
"""
import argparse
import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Lexique cgram -> dictionary part of speech. Determiners are "article" in this dictionary.
CGRAM = {'NOM': 'noun', 'VER': 'verb', 'AUX': 'verb', 'ADJ': 'adjective', 'ADV': 'adverb',
         'PRE': 'preposition', 'CON': 'conjunction', 'ONO': 'interjection', 'ADJ:num': 'numeral',
         'ADJ:pos': 'article', 'ADJ:dem': 'article', 'ADJ:ind': 'article', 'ADJ:int': 'article',
         'ART:def': 'article', 'ART:ind': 'article'}


def band(freq):
    # Same bands as build.py: occurrences per million, films + books.
    return 5 if freq >= 100 else 4 if freq >= 20 else 3 if freq >= 5 else 2 if freq >= 1 else 1


def lexique_pos_frequencies(path, normalize):
    by_pos, by_word = defaultdict(float), set()
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row.get('islem') != '1':
                continue
            cgram = row.get('cgram', '')
            pos = CGRAM.get(cgram) or ('pronoun' if cgram.startswith('PRO') else None)
            try:
                value = float(row.get('freqlemfilms2') or 0) + float(row.get('freqlemlivres') or 0)
            except ValueError:
                continue
            word = normalize(row.get('lemme', ''))
            by_word.add(word)
            if pos:
                by_pos[(word, pos)] = max(by_pos[(word, pos)], value)
    return by_pos, by_word


def apply_pos_frequencies(db, lexique, normalize):
    """Rewrite entry.frequency/freq per (word, pos). Words absent from Lexique keep 0."""
    by_pos, by_word = lexique_pos_frequencies(lexique, normalize)
    changed = 0
    for eid, word, pos, old in db.execute('SELECT id, word, pos, frequency FROM entry').fetchall():
        key = normalize(word)
        if key not in by_word:
            continue
        value = by_pos.get((key, pos))
        if value is None:
            # Function words are labelled differently across sources; keep the word value there.
            if pos in ('pronoun', 'article', 'numeral', 'conjunction', 'particle'):
                continue
            value = 0.0  # Lexique knows the word, but not in this part of speech: rare use.
        if value != old:
            db.execute('UPDATE entry SET frequency=?, freq=? WHERE id=?', (value, band(value), eid))
            changed += 1
    return changed


def main():
    from build import normalize
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('db', nargs='?', type=Path, default=ROOT / 'dist/fr-v2.sqlite')
    parser.add_argument('--lexique', type=Path, default=ROOT.parent / 'zabankhan-dict-src/Lexique383.tsv')
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        changed = apply_pos_frequencies(db, args.lexique, normalize)
        rows = dict(((w, p), (f, b)) for w, p, f, b in
                    db.execute("SELECT word, pos, frequency, freq FROM entry WHERE word='pendant'"))
    assert rows[('pendant', 'preposition')][0] > rows[('pendant', 'noun')][0], rows
    print('{} entries updated; pendant: {}'.format(changed, rows))


if __name__ == '__main__':
    main()
