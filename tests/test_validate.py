"""Regression checks for reference normalization and a complete miniature audit."""
import csv
import gzip
import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/validate.py'
spec = importlib.util.spec_from_file_location('validate', SCRIPT)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class ValidateTests(unittest.TestCase):
    def test_phonetic_normalization(self):
        self.assertEqual(v.genders('mf'), {'m', 'f'})
        self.assertEqual(v.segments('/a.p(ə).le/'), v.segments('apəle'))
        self.assertEqual(v.lex_ipa('5@§1NGR83°'), 'ɛ̃ɑ̃ɔ̃œ̃ɲŋʁɥəə')
        self.assertEqual(v.segments('\\a.kœj\\'), v.segments('/a.kœj/'))
        self.assertEqual(v.segments('[ɑ̃.n‿a]'), ('ɑ̃', 'n', 'a'))
        self.assertEqual(v.distance(v.segments('ɑ̃'), v.segments('ɑ')), 1)
        self.assertEqual(v.distance(tuple('abc'), tuple('abcde')), 2)
        with self.assertRaises(KeyError): v.lex_ipa('?')

    def test_miniature_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            with sqlite3.connect(p/'input.sqlite') as db:
                db.executescript("""
                    CREATE TABLE entry(id,word,pos,frequency,ipa,gender);
                    INSERT INTO entry VALUES(1,'chat','noun',10,'/ʃa/','m');
                    CREATE TABLE redirect(word,lemma,pos);
                    INSERT INTO redirect VALUES('chats','chat','noun');
                    CREATE TABLE sense(id,entry_id);
                    INSERT INTO sense VALUES(1,1);
                    CREATE TABLE example(sense_id,text);
                """)
            fields = ['ortho','lemme','cgram','phon','genre','freqfilms2','freqlivres','freqlemfilms2','freqlemlivres']
            with (p/'Lexique383.tsv').open('w', newline='') as f:
                w = csv.writer(f, delimiter='\t'); w.writerow(fields)
                w.writerow(['chat','chat','NOM','Sa','m',10,0,10,0])
                w.writerow(['chats','chat','NOM','Sa','m',2,0,10,0])
                # Another homograph must not turn the attested redirect into a contradiction.
                w.writerow(['chats','chater','VER','Sa','',2,0,2,0])
            with gzip.open(p/'frwiktionary-fr.jsonl.gz','wt') as f:
                f.write(json.dumps({'word':'chat','pos':'noun','tags':['masculine'],
                                    'sounds':[{'ipa':'\\ʃa\\'}],
                                    'senses':[{'examples':[{'text':'Un chat.'}]}]*4})+'\n')
            subprocess.run([sys.executable,str(SCRIPT),'--db',str(p/'input.sqlite'),
                            '--sources',str(p),'--report',str(p/'report.md'),
                            '--issues',str(p/'issues.csv')],check=True,capture_output=True)
            with (p/'issues.csv').open() as f: rows = list(csv.DictReader(f))
            kinds = [r['type'] for r in rows]
            self.assertNotIn('redirect_contradiction', kinds)
            self.assertNotIn('lexique_ipa_mismatch', kinds)
            self.assertIn('thin_entry', kinds)
            self.assertIn('example_gap_with_source', kinds)
            self.assertIn('missing_frequent_lemma', kinds)
            self.assertIn('missing_frequent_redirect', kinds)
            self.assertIn('1 / 1 shared-form redirect triples agree (100.00%)', (p/'report.md').read_text())


if __name__ == '__main__':
    unittest.main()
