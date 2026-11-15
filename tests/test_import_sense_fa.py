"""Matching uses glosses across IDs and checks position before filling."""
import contextlib
import io
import json
import sqlite3
import unittest

from tools.import_sense_fa import SOURCE, import_senses


class ImportTests(unittest.TestCase):
    def test_matching_and_no_overwrite(self):
        with sqlite3.connect(':memory:') as work, sqlite3.connect(':memory:') as pack:
            work.executescript('CREATE TABLE entry(id,word,pos,en); '
                               'CREATE TABLE sense_fa(entry_id,sense,fa,status);')
            pack.executescript('CREATE TABLE entry(id,word,pos); '
                               'CREATE TABLE sense(id,entry_id,position,en,fa); '
                               'CREATE TABLE meta(key PRIMARY KEY,value);')
            cases = [
                ('exact', ['cat'], [(4, 'cat', '')], 0, 'گربه'),
                ('normalized', ['  A   CAT!... '], [(8, 'a cat', None)], 0, 'گربه'),
                # Duplicate normalized glosses require a verified position fallback.
                ('fallback', ['cat'], [(0, 'cat.', ''), (1, 'cat', '')], 0, 'گربه'),
                ('existing', ['cat'], [(0, 'cat', 'keep')], 0, 'گربه'),
                ('mismatch', ['cat'], [(0, 'dog', '')], 0, 'گربه'),
                ('ambiguous', ['cat'], [(1, 'cat', ''), (2, 'cat', '')], 0, 'گربه'),
                ('failed', ['cat'], [(0, 'cat', '')], 0, 'گربه'),
            ]
            sid = 0
            for eid, (word, glosses, senses, position, fa) in enumerate(cases, 1):
                work.execute('INSERT INTO entry VALUES(?,?,?,?)', (eid, word, 'noun', json.dumps(glosses)))
                work.execute('INSERT INTO sense_fa VALUES(?,?,?,?)',
                             (eid, position, fa, 'failed' if word == 'failed' else 'passed'))
                pack.execute('INSERT INTO entry VALUES(?,?,?)', (eid + 100, word, 'noun'))
                for index, gloss, old_fa in senses:
                    sid += 1
                    pack.execute('INSERT INTO sense VALUES(?,?,?,?,?)', (sid, eid + 100, index, gloss, old_fa))
            with contextlib.redirect_stdout(io.StringIO()):
                counts = import_senses(work, pack)
            self.assertEqual(counts, dict(passed=6, matched=4, filled=3, skipped=3))
            self.assertEqual([r[0] for r in pack.execute('SELECT fa FROM sense ORDER BY id')],
                             ['گربه', 'گربه', 'گربه', '', 'keep', '', '', '', ''])
            self.assertEqual(pack.execute("SELECT value FROM meta WHERE key='fa_source'").fetchone()[0], SOURCE)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(import_senses(work, pack)['filled'], 0)
