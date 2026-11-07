import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from tools import build, fill_persian_v2
from unittest.mock import patch


def read_shard(path):
    data = json.loads(path.read_text())
    fields = ('id', 'word', 'pos', 'freq', 'ipa', 'gender', 'audio', 'senses', 'forms', 'expressions')
    data['entries'] = [dict(zip(fields, e)) for e in data['entries']]
    return data


def entry(word, pos, gloss='meaning', **extra):
    return dict(word=word, pos=pos, senses=[{'glosses': [gloss]}], **extra)


def inflected(word, pos, lemma, tags):
    return dict(word=word, pos=pos, senses=[{'form_of': [{'word': lemma}], 'tags': tags}])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'fr.sqlite'
        self.out = self.root / 'v2'
        rows = [entry('prendre', 'verb', forms=[{'form': 'prends', 'tags': ['indicative', 'present', 'first-person', 'singular']}]),
                entry('prendre feu', 'verb'), entry('beau', 'adj', forms=[{'form': 'belle', 'tags': ['feminine']}]),
                entry('aller', 'verb'), entry('allée', 'noun'), entry('œil', 'noun', forms=[{'form': 'yeux', 'tags': ['plural']}]),
                dict(word='rendre compte', pos='verb', senses=[{'glosses': ['to realize'], 'tags': ['reflexive']}]), entry('rendre', 'verb'),
                inflected('allé', 'verb', 'aller', ['past', 'participle', 'form-of']),
                inflected('allées', 'verb', 'allé', ['feminine', 'plural', 'form-of']),
                inflected('allées', 'noun', 'allée', ['plural', 'form-of'])]
        rows[0]['senses'] = [{'glosses': ['to take'], 'tags': ['transitive', 'botany', 'informal'],
                             'examples': [{'text': 'prends ma main', 'english': 'take my hand'}] * 3,
                             'synonyms': [{'word': 'saisir'}]}] * 10
        self.source = self.root / 'source.gz'
        with gzip.open(self.source, 'wt') as f:
            for row in rows:
                f.write(json.dumps(row) + '\n')
        self.lex = self.root / 'lex.tsv'
        self.lex.write_text('lemme\tislem\tfreqlemfilms2\tfreqlemlivres\nprendre\t1\t100\t100\n')
        self.legacy = self.root / 'v1.sqlite'
        with sqlite3.connect(self.legacy) as db:
            db.execute('CREATE TABLE entry(word, pos, fa)')
            db.execute("INSERT INTO entry VALUES('prendre','verb','گرفتن')")
        build.build_database(self.source, self.lex, self.db, self.legacy)

    def targets(self, word):
        with sqlite3.connect(self.db) as db:
            return {r[0] for r in db.execute('SELECT lemma FROM redirect WHERE word=?', (build.normalize(word),))}

    def test_redirects(self):
        for word, expected in [('prends', {'prendre'}), ('belle', {'beau'}), ('allées', {'aller', 'allée'}), ('yeux', {'œil'})]:
            self.assertEqual(self.targets(word), expected)
        with sqlite3.connect(self.db) as db:
            self.assertFalse(db.execute("SELECT 1 FROM entry WHERE word='allées'").fetchone())

    def test_reflexive(self):
        self.assertIn('se rendre compte', self.targets('rendre compte'))
        self.assertNotIn('se rendre compte', self.targets('rendre'))

    def test_senses_and_expressions(self):
        build.export_shards(self.db, self.out)
        data = read_shard(self.out / 'pr.json')
        take = next(e for e in data['entries'] if e['word'] == 'prendre')
        self.assertIn('prendre feu', take['expressions'])
        self.assertLessEqual(len(take['senses']), 8)
        self.assertEqual(take['senses'][0][2], ['transitive', 'informal'])
        self.assertEqual(len(take['senses'][0][4]), 2)
        self.assertEqual(take['senses'][0][1], 'گرفتن')
        self.assertEqual(take['senses'][0][3], ['saisir'])
        self.assertIn('prends', data['redirects'])
        target_id, label_id = data['redirects']['prends'][0]
        self.assertEqual(data['targets'][str(target_id)], ['prendre', 'verb'])
        self.assertEqual(data['form_labels'][label_id], 'ind.pres.1s')

    def test_sqlite_roundtrip_and_split(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE example SET fa='دستم را بگیر'")
        index = build.export_shards(self.db, self.out, max_bytes=400)
        self.assertIn('pr', index['split'])
        shards = [read_shard(self.out / (k + '.json')) for k in index['shards']]
        take = next(e for s in shards for e in s['entries'] if e['word'] == 'prendre')
        self.assertEqual(take['senses'][0][4][0][2], 'دستم را بگیر')
        self.assertFalse((self.out / 'pr.json').exists())

    def test_forms(self):
        raw = {'forms': [
            {'form': 'prendrais', 'tags': ['conditional', 'first-person', 'singular']},
            {'form': 'avoir + past participle', 'tags': ['infinitive', 'multiword-construction']},
            {'form': 'no-table-tags', 'tags': ['table-tags']} ]}
        forms = build.forms(raw, 'verb', 'prendre')
        self.assertEqual(forms['conditional'][0], 'prendrais')
        self.assertEqual(forms['auxiliary'], 'avoir')

    def test_rebuild_keeps_v2_translations(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE example SET fa='دستم را بگیر'")
            db.execute("UPDATE sense SET fa='برداشتن' WHERE en='to take'")
        build.build_database(self.source, self.lex, self.db, self.legacy)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT fa FROM example LIMIT 1').fetchone()[0], 'دستم را بگیر')
            self.assertEqual(db.execute("SELECT fa FROM sense WHERE en='to take'").fetchone()[0], 'برداشتن')

    def test_filler_scope_frequency_and_resume(self):
        with sqlite3.connect(self.db) as db:
            items = fill_persian_v2.pending(db, 100)
            self.assertEqual(items[0]['word'], 'prendre')
            self.assertEqual(items[0]['kind'], 'example')
            missing = len(items)
            chunk = items[:2]
            answers = {i['id']: 'ترجمه' for i in chunk}
            answers['s999999'] = 'اشتباه'
            self.assertEqual(fill_persian_v2.apply_answers(db, chunk, answers), 2)
            self.assertEqual(len(fill_persian_v2.pending(db, 100)), missing - 2)
            self.assertEqual(fill_persian_v2.apply_answers(db, chunk, answers), 0)
            with patch.object(fill_persian_v2, 'ask', side_effect=ValueError('bad JSON')) as ask:
                self.assertEqual(fill_persian_v2.fill(db, 'http://localhost', 'test', 1, 1), 1)
                self.assertEqual(ask.call_count, 3)

    def test_expression_ranking_and_reflexive_forms(self):
        with gzip.open(self.source, 'at') as f:
            rows = [entry('se prendre', 'verb'),
                    entry('prendre zut', 'verb'), entry('prendre bon', 'verb'),
                    entry('prendre très bon', 'verb'),
                    dict(word='prendre gros', pos='verb', senses=[{
                        'glosses': ['rude'], 'tags': ['derogatory']}]),
                    inflected('prends', 'verb', 'prendre feu', ['imperative']),
                    entry('prendre feu', 'verb', forms=[{'form': 'prends', 'tags': ['imperative']}])]
            rows += [entry('prendre mot' + chr(97 + i) + chr(97 + j), 'verb')
                     for i in range(2) for j in range(20)]
            for row in rows:
                f.write(json.dumps(row) + '\n')
        with self.lex.open('a') as f:
            f.write('bon\t1\t50\t50\nzut\t1\t1\t1\n')
        build.build_database(self.source, self.lex, self.db, self.legacy)
        self.assertEqual(self.targets('prends'), {'prendre', 'se prendre'})
        with sqlite3.connect(self.db) as db:
            expressions = json.loads(db.execute(
                "SELECT expressions FROM entry WHERE word='prendre' AND pos='verb'").fetchone()[0])
            self.assertEqual(len(expressions), 30)
            self.assertLess(expressions.index('prendre bon'), expressions.index('prendre zut'))
            self.assertNotIn('prendre gros', expressions)
            self.assertNotIn('prendre très bon', expressions)
            label = db.execute("SELECT form FROM redirect WHERE word='allées' AND lemma='aller'").fetchone()[0]
            self.assertEqual(label, 'pp.f.pl')

    def test_compact_labels(self):
        self.assertEqual(build.merge_labels({build.form_label(set(tags.split())) for tags in [
            'indicative present first-person singular',
            'indicative present second-person singular', 'imperative second-person singular']}),
            'imp.2s;ind.pres.1s,2s')
        self.assertEqual(build.form_label({'past', 'participle', 'feminine', 'plural'}), 'pp.f.pl')
        self.assertEqual(build.form_label({'feminine', 'singular'}), 'f.sg')

    def test_lookup_shard_key(self):
        index = {'split': {'se': ['se_'], 'de': ['des'], 'a_': ['a__'], '_i': ['_il']}}
        for word, expected in [('se rendre compte', 'se_'), ('des', 'des'),
                               ('désormais', 'des'), ('à', 'a__'), ('œil', '_il')]:
            self.assertEqual(build.lookup_shard_key(word, index), expected)
            self.assertEqual(build.lookup_shard_key(word, {}), build.shard_key(word))

    def test_recursive_lookup(self):
        self.assertEqual(build.lookup_shard_key('désormais', {'split': {'de': ['des'], 'des': ['deso']}}), 'deso')

    def test_redirect_scope(self):
        for target in ['prendre feu', 'se prendre au jeu', "s'en aller"]:
            self.assertFalse(build.redirect_allowed('prends', target, 'verb'))
        for target in ['prendre', 'se prendre', "s'abstenir"]:
            self.assertTrue(build.redirect_allowed('prends', target, 'verb'))

    def test_shard_key(self):
        for word, expected in [('École normale', 'ec'), ('à', 'a_'), ('œil', '_i'), ('', '__'), ("s’en aller", 's_')]:
            self.assertEqual(build.shard_key(word), expected)


@unittest.skipUnless((build.ROOT / 'dist/fr-v2.sqlite').exists(), 'run tools/build.py for full-data tests')
class BuiltDataTests(unittest.TestCase):
    def test_real_redirects_and_reflexive(self):
        with sqlite3.connect('file:' + str(build.ROOT / 'dist/fr-v2.sqlite') + '?mode=ro', uri=True) as db:
            for word, targets in [('prends', {'prendre'}), ('belle', {'beau'}), ('allées', {'aller', 'allée'}), ('yeux', {'œil'}),
                                  ('rendre compte', {'se rendre compte'})]:
                actual = {r[0] for r in db.execute('SELECT lemma FROM redirect WHERE word=?', (word,))}
                self.assertTrue(targets <= actual, (word, actual))
            expressions = json.loads(db.execute("SELECT expressions FROM entry WHERE word='prendre' AND pos='verb'").fetchone()[0])
            self.assertIn('prendre feu', expressions)
            self.assertEqual(len(expressions), len(set(expressions)))
            self.assertLessEqual(len(expressions), 30)
            self.assertEqual({r[0] for r in db.execute(
                "SELECT lemma FROM redirect WHERE word='prends'")}, {'prendre', 'se prendre'})
            for source, target, pos in db.execute('SELECT word,lemma,pos FROM redirect'):
                self.assertTrue(build.redirect_allowed(source, target, pos), (source, target))
            forms = json.loads(db.execute("SELECT forms FROM entry WHERE word='prendre' AND pos='verb'").fetchone()[0])
            for tense in ['present', 'imperfect', 'future', 'conditional', 'subjunctive']:
                self.assertEqual(len(forms[tense]), 6)
                self.assertTrue(all(forms[tense]))
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_real_shard_sizes(self):
        output = build.ROOT / 'fr/v2'
        index = json.loads((output / 'index.json').read_text())
        self.assertTrue(index['split'])
        self.assertLess(sum((output / (key + '.json')).stat().st_size for key in index['shards']), 50000000)
        for key in index['shards']:
            self.assertLessEqual((output / (key + '.json')).stat().st_size, 999999)


if __name__ == '__main__':
    unittest.main()
