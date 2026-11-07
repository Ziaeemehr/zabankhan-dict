#!/usr/bin/env python3
"""Cross-check v2 against local Lexique 3.83 and French Wiktionary; Python 3.9 stdlib.

Run from any directory. Inputs are read-only; only the two output paths are written.
See the generated report for normalization, denominators and source limitations.
"""
import argparse
import re
import csv
import gzip
import json
import sqlite3
import unicodedata as ud
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Manuel Lexique 3, table 2 and appendix B. 3 is non-elidable schwa.
PHON = dict(zip('OE°32951@§SZNRG8x',
                ['ɔ', 'ɛ', 'ə', 'ə', 'ø', 'œ', 'ɛ̃', 'œ̃', 'ɑ̃', 'ɔ̃',
                 'ʃ', 'ʒ', 'ɲ', 'ʁ', 'ŋ', 'ɥ', 'x']))
PHON.update({c: c for c in 'aiyuoeptkbdgfvs zmnljw'.replace(' ', '')})
LEX_POS = {'NOM': 'noun', 'VER': 'verb', 'AUX': 'verb', 'ADJ': 'adjective',
           'ADV': 'adverb', 'PRE': 'preposition', 'CON': 'conjunction',
           'ONO': 'interjection', 'ADJ:num': 'numeral'}
FR_POS = {'adj': 'adjective', 'adv': 'adverb', 'prep': 'preposition',
          'pron': 'pronoun', 'conj': 'conjunction', 'intj': 'interjection',
          'num': 'numeral', 'det': 'determiner', 'name': 'proper-noun',
          'character': 'character', 'phrase': 'phrase'}


RAW = False

def norm(s):
    value = ud.normalize('NFC', ' '.join(s.replace('’', "'").split())).lower()
    return value if RAW else value.replace('œ', 'oe').replace('æ', 'ae')

def compatible(word, ours, theirs):
    if ours == theirs: return True
    determiners = {'tout','tous','toute','toutes','quel','quelle','quels','quelles','aucun','aucune','aucuns','aucunes','chaque','certain','certaine','certains','certaines'}
    return not RAW and norm(word) in determiners and ours in {'article','pronoun','determiner'} and theirs == 'adjective'


def lex_pos(s):
    if s.startswith('PRO'): return 'pronoun'
    if s.startswith('ART'): return 'article'
    if s.startswith('ADJ:') and s != 'ADJ:num': return 'determiner'
    return LEX_POS.get(s)


def lex_ipa(s):
    return ''.join(PHON[c] for c in s if not c.isspace() and c != '-')


def segments(s):
    """NFD base+combining-mark clusters: nasalization is part of its vowel."""
    result = []
    for c in ud.normalize('NFD', s):
        if c.isspace() or c in '/\\[]().·‧‿⁀͜͡ˈˌ': continue
        if ud.combining(c) and result: result[-1] += c
        else: result.append(c)
    return tuple(ud.normalize('NFC', c) for c in result)


def distance(a, b):
    """Levenshtein distance capped at 2 (only exact/one/more are needed)."""
    if abs(len(a) - len(b)) > 1: return 2
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        row = [i]
        for j, y in enumerate(b, 1):
            row.append(min(row[-1] + 1, prev[j] + 1, prev[j-1] + (x != y)))
        prev = row
    return min(2, prev[-1])


def genders(s):
    if s in ('mf', 'fm'): return {'m', 'f'}
    return {g for g, names in [('m', ('m', 'masculine')), ('f', ('f', 'feminine'))]
            if any(n in s.replace(',', ' ').replace('/', ' ').split() for n in names)}


def blank_ref():
    return {'ipa': set(), 'gender': set(), 'senses': 0, 'examples': False}


def pct(n, d):
    return '{:.2f}%'.format(100 * n / d) if d else 'N/A'


class Results:
    def __init__(self, writer):
        self.writer = writer
        self.counts = Counter()
        self.samples = defaultdict(list)

    def issue(self, kind, word, pos, ours, theirs):
        row = [kind, word, pos, str(ours), str(theirs)]
        self.writer.writerow(row)
        self.counts[kind] += 1
        if len(self.samples[kind]) < 15: self.samples[kind].append(row)

    def table(self, kinds):
        rows = [r for k in kinds for r in self.samples[k]][:15]
        if not rows: return '\nNo disagreements.\n'
        def esc(x): return x.replace('|', '\\|').replace('\n', ' ')
        return '\n| Type | Word | POS | Ours | Reference |\n|---|---|---|---|---|\n' + ''.join(
            '| ' + ' | '.join(esc(x) for x in r) + ' |\n' for r in rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', type=Path, default=ROOT/'dist/fr-v2.sqlite')
    ap.add_argument('--sources', type=Path, default=Path.home()/'git/zabankhan-dict-src')
    ap.add_argument('--report', type=Path, default=ROOT/'docs/validation-report.md')
    ap.add_argument('--issues', type=Path, default=ROOT/'validation/issues.csv')
    ap.add_argument('--raw', action='store_true')
    ap.add_argument('--metrics', type=Path)
    ap.add_argument('--before', type=Path)
    args = ap.parse_args()
    global RAW
    RAW = args.raw
    with sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        entries = [dict(r) for r in db.execute('SELECT * FROM entry ORDER BY frequency DESC, word, pos, id')]
        redirects = list(db.execute('SELECT word,lemma,pos FROM redirect ORDER BY word,lemma,pos'))
        sense_counts = dict(db.execute('SELECT entry_id,count(*) FROM sense GROUP BY entry_id'))
        missing_examples = dict(db.execute('SELECT entry_id,count(*) FROM sense s WHERE NOT EXISTS '
                                          "(SELECT 1 FROM example e WHERE e.sense_id=s.id AND trim(e.text)!='') GROUP BY entry_id"))
    words = {norm(e['word']) for e in entries}
    keys = {(norm(e['word']), e['pos']) for e in entries}
    lex = defaultdict(blank_ref)
    lex_targets = defaultdict(set)
    frequent_forms = defaultdict(float)
    frequent_lemmas = defaultdict(float)
    lex_rows = 0
    ignored_pos = Counter()
    with (args.sources/'Lexique383.tsv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            lex_rows += 1
            word, lemma, pos = norm(r['ortho']), norm(r['lemme']), lex_pos(r['cgram'])
            if not pos:
                ignored_pos[r['cgram']] += 1
                continue
            freq = max(float(r['freqfilms2'] or 0), float(r['freqlivres'] or 0))
            ref = lex[word, pos]
            if r['phon']: ref['ipa'].add(segments(lex_ipa(r['phon'])))
            ref['gender'].update(genders(r['genre']))
            lex_targets[word].add((lemma, pos))
            if word != lemma and freq > 1:
                frequent_forms[word, lemma, pos] = max(frequent_forms[word, lemma, pos], freq)
            # Lemma-level frequencies include the full inflection paradigm.
            lf = max(float(r['freqlemfilms2'] or 0), float(r['freqlemlivres'] or 0))
            if lf > 1: frequent_lemmas[lemma] = max(frequent_lemmas[lemma], lf)
    print('Loaded {:,} entries and {:,} Lexique rows; streaming French Wiktionary…'.format(len(entries), lex_rows), flush=True)
    fr = defaultdict(blank_ref)
    fr_words = set()
    fr_rows = 0
    with gzip.open(args.sources/'frwiktionary-fr.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r.get('lang_code', 'fr') != 'fr': continue
            fr_rows += 1
            word = norm(r.get('word', ''))
            if word not in words: continue
            fr_words.add(word)
            pos = FR_POS.get(r.get('pos'), r.get('pos'))
            ref = fr[word, pos]
            ref['ipa'].update(segments(s['ipa']) for s in r.get('sounds', []) if s.get('ipa'))
            ss = r.get('senses', [])
            ref['senses'] += len(ss)
            ref['gender'].update(genders(' '.join(r.get('tags', []))))
            for s in ss:
                ref['gender'].update(genders(' '.join(s.get('tags', []))))
                if any(e.get('text', '').strip() for e in s.get('examples', [])): ref['examples'] = True
    args.issues.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    sections = []
    with args.issues.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f); writer.writerow(['type', 'word', 'pos', 'ours', 'theirs'])
        out = Results(writer)
        overlap = agree = reflexive_differences = 0
        redirect_set = {(norm(w), norm(l), p) for w, l, p in redirects}
        for w, l, p in redirects:
            if norm(w) not in lex_targets: continue
            overlap += 1
            bare = re.sub(r"^(?:se |s')", '', norm(l))
            attested = any(norm(l) == a and compatible(w,p,b) for a,b in lex_targets[norm(w)])
            reflexive = p == 'verb' and bare != norm(l) and ((bare,p) in lex_targets[norm(w)] or (norm(w),bare,p) in redirect_set)
            if attested or (not RAW and reflexive): agree += 1
            else:
                bare = norm(l)
                if bare.startswith('se '): bare = bare[3:]
                elif bare.startswith("s'"): bare = bare[2:]
                if bare != norm(l) and (bare, p) in lex_targets[norm(w)]: reflexive_differences += 1
                out.issue('redirect_contradiction', w, p, l, '; '.join(a+' ('+b+')' for a,b in sorted(lex_targets[norm(w)])))
        for (w, l, p), freq in sorted(frequent_forms.items(), key=lambda x: (-x[1], x[0])):
            if not any((w,l,op) in redirect_set and compatible(w,op,p) for op in {p,'article','pronoun','determiner'}):
                out.issue('missing_frequent_redirect', w, p, 'no redirect', '{}; freq={:g}'.format(l,freq))
        sections.append('## 1. Redirects\n\n{} / {} shared-form redirect triples agree ({}); {} contradictions. '
                        '{} frequent Lexique form→lemma+POS triples lack a redirect (including forms that are also headwords).\n'.format(
                            agree, overlap, pct(agree,overlap), overlap-agree, out.counts['missing_frequent_redirect'])
                        + '\nFrequent Lexique redirect coverage: {}/{} ({}).\n'.format(len(frequent_forms)-out.counts['missing_frequent_redirect'], len(frequent_forms), pct(len(frequent_forms)-out.counts['missing_frequent_redirect'],len(frequent_forms))) + '\nOf the contradictions, {} differ only by our reflexive se/s’ prefix. These require contextual review, not blanket removal.\n'.format(reflexive_differences) + out.table(['redirect_contradiction']) + '\nFrequent missing redirects:\n' + out.table(['missing_frequent_redirect']))
        summaries = []
        for source, refs in [('Lexique', lex), ('French Wiktionary', fr)]:
            prefix = 'lexique' if source == 'Lexique' else 'frwiktionary'
            stats = Counter()
            poses = defaultdict(set)
            for w,p in refs: poses[w].add(p)
            for e in entries:
                w,p = norm(e['word']),e['pos']; ref = refs.get((w,p))
                if w in poses:
                    stats['pos_total'] += 1
                    if any(compatible(w,p,rp) for rp in poses[w]): stats['pos_match'] += 1
                    else: out.issue(prefix+'_pos',e['word'],p,p,', '.join(sorted(poses[w])))
                if not ref: continue
                ours = segments(e['ipa'])
                if ref['ipa'] and ours:
                    d = min(distance(ours, other) for other in ref['ipa'])
                    kind = ['exact','near','mismatch'][d]; stats[kind] += 1
                    if d: out.issue(prefix+'_ipa_'+kind, e['word'], p, e['ipa'], '; '.join(''.join(s) for s in sorted(ref['ipa'])))
                elif ref['ipa']:
                    stats['ipa_missing_ours'] += 1
                    out.issue(prefix+'_ipa_missing',e['word'],p,'', '; '.join(''.join(s) for s in sorted(ref['ipa'])))
                else: stats['ipa_missing_reference'] += 1
                if ref['gender'] and p == 'noun':
                    og = genders(e['gender']); stats['gender_total'] += 1
                    if og & ref['gender']: stats['gender_match'] += 1
                    else: out.issue(prefix+'_gender',e['word'],p,e['gender'], '/'.join(sorted(ref['gender'])))
            total = sum(stats[k] for k in ['exact','near','mismatch'])
            summaries.append((source, prefix, stats, total))
        ipa_text = '## 2. IPA\n\n| Source | Compared | Exact | Near (1 edit) | Mismatch | Missing ours | Missing reference on shared word+POS |\n|---|---:|---:|---:|---:|---:|---:|\n'
        pos_text = '## 3. POS and gender\n\n| Source | POS agreement / shared-word entries | Gender agreement / reference-gender entries |\n|---|---|---|\n'
        for source, prefix, st, total in summaries:
            ipa_text += '| {} | {} | {} ({}) | {} ({}) | {} ({}) | {} | {} |\n'.format(source,total,st['exact'],pct(st['exact'],total),st['near'],pct(st['near'],total),st['mismatch'],pct(st['mismatch'],total),st['ipa_missing_ours'],st['ipa_missing_reference'])
            pos_text += '| {} | {}/{} ({}) | {}/{} ({}) |\n'.format(source,st['pos_match'],st['pos_total'],pct(st['pos_match'],st['pos_total']),st['gender_match'],st['gender_total'],pct(st['gender_match'],st['gender_total']))
        for source,prefix,st,total in summaries:
            ipa_text += '\n'+source+' IPA disagreements:\n'+out.table([prefix+'_ipa_mismatch',prefix+'_ipa_near',prefix+'_ipa_missing'])
            pos_text += '\n'+source+' POS disagreements:\n'+out.table([prefix+'_pos'])+'\nGender disagreements:\n'+out.table([prefix+'_gender'])
        sections.extend([ipa_text,pos_text])
        for w,freq in sorted(frequent_lemmas.items(),key=lambda x:(-x[1],x[0])):
            if w not in words: out.issue('missing_frequent_lemma',w,'','absent','freq={:g}'.format(freq))
        covered = len(frequent_lemmas.keys() & words)
        fr_covered = sum(norm(e['word']) in fr_words for e in entries)
        sections.append('## 4. Headword coverage\n\nFrequent Lexique lemmas present: {}/{} ({}). Our entry rows with a French Wiktionary word: {}/{} ({}).\n'.format(covered,len(frequent_lemmas),pct(covered,len(frequent_lemmas)),fr_covered,len(entries),pct(fr_covered,len(entries)))+out.table(['missing_frequent_lemma']))
        top = entries[:5000]; shared = equal = thin = 0
        for e in top:
            ref = fr.get((norm(e['word']),e['pos'])); n = sense_counts.get(e['id'],0)
            if not ref:
                out.issue('top_senses_no_word_pos',e['word'],e['pos'],n,'no word+POS'); continue
            shared += 1; m = ref['senses']; equal += n == m
            if n != m: out.issue('top_sense_count',e['word'],e['pos'],n,m)
            if n == 1 and m >= 4:
                thin += 1; out.issue('thin_entry',e['word'],e['pos'],n,m)
        sections.append('## 5. Senses (top frequency entries)\n\nSame word+POS: {}/{} ({}). Equal sense counts among shared pairs: {}/{} ({}). Likely thin (ours=1, reference≥4): {} ({} of shared pairs).\n'.format(shared,len(top),pct(shared,len(top)),equal,shared,pct(equal,shared),thin,pct(thin,shared))+out.table(['thin_entry'])+'\nOther count disagreements:\n'+out.table(['top_sense_count','top_senses_no_word_pos']))
        potential_entries = potential_senses = 0
        for e in entries:
            n = missing_examples.get(e['id'],0)
            if not n: continue
            ref = fr.get((norm(e['word']),e['pos']))
            if ref and ref['examples']:
                potential_entries += 1; potential_senses += n
                out.issue('example_gap_with_source',e['word'],e['pos'],'{} senses without examples'.format(n),'French examples available at word+POS')
        total_senses = sum(sense_counts.values()); missing = sum(missing_examples.values())
        sections.append('## 6. Examples\n\n{} / {} senses lack nonempty examples ({}); example coverage/agreement with the completeness goal: {}. '
                        '{} entries contain those gaps; {} have French Wiktionary examples at the same word+POS ({}), covering {} candidate senses ({} of missing senses). '
                        'These are entry-level candidates, not aligned sense translations.\n'.format(missing,total_senses,pct(missing,total_senses),pct(total_senses-missing,total_senses),len(missing_examples),potential_entries,pct(potential_entries,len(missing_examples)),potential_senses,pct(potential_senses,missing))+out.table(['example_gap_with_source']))
    verdict = '# Dictionary v2 validation\n\n## Verdict\n\n'
    verdict += '- Redirect consistency with Lexique: {} agreement on shared forms; inspect {} contradictions and {} frequent missing links.\n'.format(pct(agree,overlap),overlap-agree,out.counts['missing_frequent_redirect'])
    for source,prefix,st,total in summaries:
        verdict += '- {}: IPA {} exact / {} exact-or-near; POS {}; gender {}. These measure agreement, not proven correctness.\n'.format(source,pct(st['exact'],total),pct(st['exact']+st['near'],total),pct(st['pos_match'],st['pos_total']),pct(st['gender_match'],st['gender_total']))
    verdict += '- Coverage: {} of frequent Lexique lemmas; {} of our entry rows have a French Wiktionary word.\n'.format(pct(covered,len(frequent_lemmas)),pct(fr_covered,len(entries)))
    verdict += '- Sense completeness needs review: {} likely thin entries in the top {}; examples cover {} of senses.\n'.format(thin,len(top),pct(total_senses-missing,total_senses))
    verdict += '\nFixes worth making: review redirect contradictions and frequent missing forms/lemmas first; inspect POS/gender differences before changing homographs; review IPA mismatches using regional variants; enrich the flagged thin entries; consider French examples for the {} candidate entries after sense alignment. No automatic corrections are made.\n'.format(potential_entries)
    methods = '''\n## Method and limitations\n\n- Lexique is already a build input, so it is a consistency reference, **not independent ground truth**. The two Wiktionaries are separate language editions/extractions but may share material. Disagreement does not prove an error.
- Words: NFC, lowercase, curly apostrophe→ASCII, collapsed whitespace; accents retained. Coverage uses headwords, not redirects. Entry denominators count word+POS rows; lemma coverage counts distinct words.
- Redirects: each of our (form, lemma, POS) triples is tested against all Lexique analyses of the form. Other homograph analyses do not contradict an attested triple. Missing frequent links are individual nonidentity triples, even if another analysis or a headword exists.
- Frequent forms: max(freqfilms2, freqlivres)>1 per million. Frequent lemmas: max(freqlemfilms2, freqlemlivres)>1 over lemma analyses, rather than the frequency of an individual inflection. Top 5,000 are entry rows sorted by numeric frequency descending, then word, POS, id.
- POS mapping: NOM→noun, VER/AUX→verb, ADJ→adjective, ADV→adverb, PRE→preposition, CON→conjunction, ONO→interjection, PRO*→pronoun, ART*→article, ADJ:num→numeral, other ADJ:*→determiner. LIA and unknown categories are excluded and counted below. French Wiktionary abbreviations adj/adv/prep/pron/conj/intj/num/det/name map to adjective/adverb/preposition/pronoun/conjunction/interjection/numeral/determiner/proper-noun. Other POS labels are retained. POS is tested against all reference POS at the word; IPA/gender require the same POS.
- Lexique phon mapping follows local `Manuel_Lexique.3.pdf`, table 2 (p.12), appendix B: `O→ɔ E→ɛ °→ə 3→ə 2→ø 9→œ 5→ɛ̃ 1→œ̃ @→ɑ̃ §→ɔ̃ S→ʃ Z→ʒ N→ɲ R→ʁ G→ŋ 8→ɥ x→x`; `a i y u o e p t k b d g f v s z m n l j w` retain their IPA values. Spaces/hyphens are separators. Unknown codes fail rather than silently passing through.
- IPA: remove /, backslashes, brackets, whitespace, syllable dots, stress, parentheses and liaison/tie marks; retain vowel quality, nasalization, length and consonants (including liaison consonants). NFD base+combining-mark clusters count as segments; Levenshtein insertion/deletion/substitution distance 0 is exact, 1 near, ≥2 mismatch. Best distance over all reference variants wins. Near matches are not necessarily linguistically equivalent. Missing IPA is excluded from match denominators and reported separately; contextual audio pronunciations can cause noise.
- Gender: union of m/f (including SQLite `mf`) or masculine/feminine tags at entry and sense level; any overlap agrees. Missing ours counts as a disagreement when reference gender exists; absent reference gender is excluded. No gender is inferred from inflected forms. Adjusted gender rates include nouns only. Adjusted words equate œ/oe and æ/ae. Reflexive redirects agree if the plain verb is attested by Lexique or by another redirect for that form. Listed determiner adjectives are compatible with our article/pronoun/determiner POS. Raw mode retains literal words, exact POS and all-POS gender.
- French records with the same word+POS are aggregated across etymologies; sense counts sum extracted senses, including form-of senses. Counts are structural signals, not semantic alignment; ours are capped at eight. Examples require nonblank text. French examples are candidate sources only; meaning alignment and licensing/attribution need review before reuse.
- CSV contains every flagged issue (including near IPA, unequal top-entry sense counts and example candidates); report tables show at most 15 per category, ordered by our frequency except redirects (alphabetical) and missing Lexique items (reference frequency). N/A means no comparable records. Percentages are unweighted.
'''
    methods += '\nInputs: `{}`, `{}`, `{}`.\n\nLoaded {:,} SQLite entries, {:,} redirects, {:,} Lexique rows, {:,} French records. Excluded Lexique POS rows: {}. CSV issues: {:,}.\n'.format(args.db,args.sources/'Lexique383.tsv',args.sources/'frwiktionary-fr.jsonl.gz',len(entries),len(redirects),lex_rows,fr_rows,dict(ignored_pos),sum(out.counts.values()))
    metrics = {'Redirect agreement': pct(agree,overlap), 'Redirect contradictions': overlap-agree, 'Missing frequent redirects': out.counts['missing_frequent_redirect'], 'Frequent lemma coverage': pct(covered,len(frequent_lemmas)), 'Senses with example': total_senses-missing}
    for source,prefix,st,total in summaries:
        metrics[source+' POS'] = pct(st['pos_match'],st['pos_total'])
        metrics[source+' gender'] = pct(st['gender_match'],st['gender_total'])
    if args.metrics: args.metrics.write_text(json.dumps(metrics,indent=2))
    if not RAW:
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            subprocess.run(['python3',str(Path(__file__).resolve()),'--raw','--db',str(args.db),'--sources',str(args.sources),'--report',str(td/'raw.md'),'--issues',str(td/'raw.csv'),'--metrics',str(td/'raw.json')], check=True, stdout=subprocess.DEVNULL)
            raw = json.loads((td/'raw.json').read_text())
        table = '| Metric | Adjusted | Raw |\n|---|---:|---:|\n' + ''.join('| {} | {} | {} |\n'.format(k,v,raw[k]) for k,v in metrics.items()) + '\n'
        if args.before:
            before = json.loads(args.before.read_text())
            table = '| Metric | Before | After |\n|---|---:|---:|\n' + ''.join('| {} | {} | {} |\n'.format(k,before.get(k,'N/A'),v) for k,v in metrics.items()) + '\n' + table
        verdict = verdict.replace('## Verdict\n\n','## Verdict\n\n'+table)
    args.report.write_text(verdict + methods + '\n' + '\n\n'.join(sections),encoding='utf-8')
    print(verdict)
    print('Wrote {} and {} ({} issues)'.format(args.report,args.issues,sum(out.counts.values())))


if __name__ == '__main__':
    main()
