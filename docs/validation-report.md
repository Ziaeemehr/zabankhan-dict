# Dictionary v2 validation

## Verdict

| Metric | Adjusted | Raw |
|---|---:|---:|
| Redirect agreement | 92.39% | 79.10% |
| Redirect contradictions | 8263 | 22658 |
| Missing frequent redirects | 608 | 637 |
| Frequent lemma coverage | 93.79% | 93.61% |
| Senses with example | 13663 | 13663 |
| Lexique POS | 94.38% | 94.38% |
| Lexique gender | 98.35% | 98.35% |
| French Wiktionary POS | 97.45% | 97.44% |
| French Wiktionary gender | 94.71% | 94.72% |

- Redirect consistency with Lexique: 92.39% agreement on shared forms; inspect 8263 contradictions and 608 frequent missing links.
- Lexique: IPA 66.95% exact / 93.63% exact-or-near; POS 94.38%; gender 98.35%. These measure agreement, not proven correctness.
- French Wiktionary: IPA 88.83% exact / 97.59% exact-or-near; POS 97.45%; gender 94.71%. These measure agreement, not proven correctness.
- Coverage: 93.79% of frequent Lexique lemmas; 91.53% of our entry rows have a French Wiktionary word.
- Sense completeness needs review: 906 likely thin entries in the top 5000; examples cover 12.22% of senses.

Fixes worth making: review redirect contradictions and frequent missing forms/lemmas first; inspect POS/gender differences before changing homographs; review IPA mismatches using regional variants; enrich the flagged thin entries; consider French examples for the 63511 candidate entries after sense alignment. No automatic corrections are made.

## Method and limitations

- Lexique is already a build input, so it is a consistency reference, **not independent ground truth**. The two Wiktionaries are separate language editions/extractions but may share material. Disagreement does not prove an error.
- Words: NFC, lowercase, curly apostrophe→ASCII, collapsed whitespace; accents retained. Coverage uses headwords, not redirects. Entry denominators count word+POS rows; lemma coverage counts distinct words.
- Redirects: each of our (form, lemma, POS) triples is tested against all Lexique analyses of the form. Other homograph analyses do not contradict an attested triple. Missing frequent links are individual nonidentity triples, even if another analysis or a headword exists.
- Frequent forms: max(freqfilms2, freqlivres)>1 per million. Frequent lemmas: max(freqlemfilms2, freqlemlivres)>1 over lemma analyses, rather than the frequency of an individual inflection. Top 5,000 are entry rows sorted by numeric frequency descending, then word, POS, id.
- POS mapping: NOM→noun, VER/AUX→verb, ADJ→adjective, ADV→adverb, PRE→preposition, CON→conjunction, ONO→interjection, PRO*→pronoun, ART*→article, ADJ:num→numeral, other ADJ:*→determiner. LIA and unknown categories are excluded and counted below. French Wiktionary abbreviations adj/adv/prep/pron/conj/intj/num/det/name map to adjective/adverb/preposition/pronoun/conjunction/interjection/numeral/determiner/proper-noun. Other POS labels are retained. POS is tested against all reference POS at the word; IPA/gender require the same POS.
- Lexique phon mapping follows local `Manuel_Lexique.3.pdf`, table 2 (p.12), appendix B: `O→ɔ E→ɛ °→ə 3→ə 2→ø 9→œ 5→ɛ̃ 1→œ̃ @→ɑ̃ §→ɔ̃ S→ʃ Z→ʒ N→ɲ R→ʁ G→ŋ 8→ɥ x→x`; `a i y u o e p t k b d g f v s z m n l j w` retain their IPA values. Spaces/hyphens are separators. Unknown codes fail rather than silently passing through.
- IPA: remove /, backslashes, brackets, whitespace, syllable dots, stress, parentheses and liaison/tie marks; retain vowel quality, nasalization, length and consonants (including liaison consonants). NFD base+combining-mark clusters count as segments; Levenshtein insertion/deletion/substitution distance 0 is exact, 1 near, ≥2 mismatch. Best distance over all reference variants wins. Near matches are not necessarily linguistically equivalent. Missing IPA is excluded from match denominators and reported separately; contextual audio pronunciations can cause noise.
- Gender: union of m/f (including SQLite `mf`) or masculine/feminine tags at entry and sense level; any overlap agrees. Missing ours counts as a disagreement when reference gender exists; absent reference gender is excluded. No gender is inferred from inflected forms. Adjusted gender rates include nouns only. Adjusted words equate œ/oe and æ/ae. Reflexive redirects agree if the plain verb is attested by Lexique or by another redirect for that form. Listed determiner adjectives are compatible with our article/pronoun/determiner POS. Raw mode retains literal words, exact POS and all-POS gender.
- French records with the same word+POS are aggregated across etymologies; sense counts sum extracted senses, including form-of senses. Counts are structural signals, not semantic alignment; ours are capped at eight. Examples require nonblank text. French examples are candidate sources only; meaning alignment and licensing/attribution need review before reuse.
- CSV contains every flagged issue (including near IPA, unequal top-entry sense counts and example candidates); report tables show at most 15 per category, ordered by our frequency except redirects (alphabetical) and missing Lexique items (reference frequency). N/A means no comparable records. Percentages are unweighted.

Inputs: `/Users/ziaee/git/zabankhan-dict/dist/fr-v2.sqlite`, `/Users/ziaee/git/zabankhan-dict-src/Lexique383.tsv`, `/Users/ziaee/git/zabankhan-dict-src/frwiktionary-fr.jsonl.gz`.

Loaded 88,673 SQLite entries, 436,336 redirects, 142,694 Lexique rows, 2,112,393 French records. Excluded Lexique POS rows: {'LIA': 1, '': 8}. CSV issues: 123,017.

## 1. Redirects

100263 / 108526 shared-form redirect triples agree (92.39%); 8263 contradictions. 608 frequent Lexique form→lemma+POS triples lack a redirect (including forms that are also headwords).

Frequent Lexique redirect coverage: 21452/22060 (97.24%).

Of the contradictions, 0 differ only by our reflexive se/s’ prefix. These require contextual review, not blanket removal.

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| redirect_contradiction | a capella | adjective | a cappella | a capella (adverb) |
| redirect_contradiction | a capella | adverb | a cappella | a capella (adverb) |
| redirect_contradiction | abaisses | noun | abaisse | abaisser (verb) |
| redirect_contradiction | abandonneurs | adjective | abandonneur | abandonneur (noun) |
| redirect_contradiction | abandonnés | noun | abandonné | abandonner (verb); abandonné (adjective) |
| redirect_contradiction | abasourdissant | verb | abasourdir | abasourdissant (adjective) |
| redirect_contradiction | abattants | adjective | abattant | abattant (noun) |
| redirect_contradiction | abattement | noun | abattage | abattement (noun) |
| redirect_contradiction | abattements | noun | abattage | abattement (noun) |
| redirect_contradiction | abattures | noun | abattage | abatture (noun) |
| redirect_contradiction | abbatiales | noun | abbatiale | abbatial (adjective) |
| redirect_contradiction | abbesses | noun | abbesse | abbé (noun) |
| redirect_contradiction | abbé | noun | abbesse | abbé (noun) |
| redirect_contradiction | abbés | noun | abbesse | abbé (noun) |
| redirect_contradiction | abdos | noun | abdo | abdos (noun) |

Frequent missing redirects:

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| missing_frequent_redirect | n' | adverb | no redirect | ne; freq=8860.45 |
| missing_frequent_redirect | millions | noun | no redirect | million; freq=87.92 |
| missing_frequent_redirect | meilleure | adjective | no redirect | meilleur; freq=73.69 |
| missing_frequent_redirect | n | adverb | no redirect | ne; freq=70.36 |
| missing_frequent_redirect | nouvelles | adjective | no redirect | nouvelle; freq=41.69 |
| missing_frequent_redirect | amis | adjective | no redirect | ami; freq=34.27 |
| missing_frequent_redirect | meilleurs | adjective | no redirect | meilleur; freq=32.64 |
| missing_frequent_redirect | seule | noun | no redirect | seul; freq=31.04 |
| missing_frequent_redirect | molle | adjective | no redirect | mou,mol; freq=22.7 |
| missing_frequent_redirect | dernière | noun | no redirect | dernier; freq=22.57 |
| missing_frequent_redirect | re | adverb | no redirect | r; freq=21.43 |
| missing_frequent_redirect | infos | noun | no redirect | info; freq=18.78 |
| missing_frequent_redirect | meilleures | adjective | no redirect | meilleur; freq=15.25 |
| missing_frequent_redirect | milliards | noun | no redirect | milliard; freq=13.49 |
| missing_frequent_redirect | moindres | adjective | no redirect | moindre; freq=13.31 |


## 2. IPA

| Source | Compared | Exact | Near (1 edit) | Mismatch | Missing ours | Missing reference on shared word+POS |
|---|---:|---:|---:|---:|---:|---:|
| Lexique | 32238 | 21582 (66.95%) | 8602 (26.68%) | 2054 (6.37%) | 4452 | 0 |
| French Wiktionary | 61776 | 54876 (88.83%) | 5414 (8.76%) | 1486 (2.41%) | 15137 | 2182 |

Lexique IPA disagreements:

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| lexique_ipa_mismatch | prévenir | verb | /pʁev.niʁ/ | pʁɛvəniʁ |
| lexique_ipa_mismatch | cent | noun | /sɛnt/ | sɑ̃ |
| lexique_ipa_mismatch | supporter | noun | /sy.pɔʁ.tɛʁ/ | sypoʁtœʁ |
| lexique_ipa_mismatch | regretter | verb | /ʁə.ɡʁɛ.te/ | ʁəgʁete |
| lexique_ipa_mismatch | élever | verb | /el.ve/ | ɛləve |
| lexique_ipa_mismatch | colonel | noun | /kɔ.lɔ.nɛl/ | kolonɛl |
| lexique_ipa_mismatch | ranger | noun | /ʁɑ̃.dʒœʁ/ | ʁɑ̃ʒɛʁ |
| lexique_ipa_mismatch | événement | noun | /e.ven.mɑ̃/ | evɛnəmɑ̃ |
| lexique_ipa_mismatch | également | adverb | /e.ɡal.mɑ̃/ | egaləmɑ̃ |
| lexique_ipa_mismatch | heureusement | adverb | /œ.ʁøz.mɑ̃/ | øʁøzəmɑ̃ |
| lexique_ipa_mismatch | kilomètre | noun | /ki.lɔ.mɛːtʁ/ | kilomɛtʁ |
| lexique_ipa_mismatch | ben | noun | /bɛn/ | bɛ̃ |
| lexique_ipa_mismatch | provoquer | verb | /pʁɔ.vɔ.ke/ | pʁovoke |
| lexique_ipa_mismatch | rigoler | verb | /ʁi.ɡɔ.le/ | ʁigole |
| lexique_ipa_mismatch | programme | noun | /pʁɔ.ɡʁam/ | pʁogʁam |

French Wiktionary IPA disagreements:

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| frwiktionary_ipa_mismatch | hé | interjection | /e/ | ^haspirée |
| frwiktionary_ipa_mismatch | hé | noun | /e/ | ^haspirée |
| frwiktionary_ipa_mismatch | hier | verb | /je/ | ^haspiréije; ^haspiréje; ijɛʁ; jaɛ̯ʁ,ijaɛ̯ʁ; jɛʁ; jɛʁ,ijɛʁ |
| frwiktionary_ipa_mismatch | hôpital | noun | /o.pi.tal/ | ^hmuetopital; ^hmuetɔpital; ɛ̃nopital |
| frwiktionary_ipa_mismatch | hasard | noun | /a.zaʁ/ | ^haspiréazaʁ; ləazaʁ |
| frwiktionary_ipa_mismatch | habit | noun | /a.bi/ | ^hmuetabi; œ̃nabi |
| frwiktionary_ipa_mismatch | habitant | noun | /a.bi.tɑ̃/ | ^hmuetabitɑ̃ |
| frwiktionary_ipa_mismatch | hocher | verb | /ɔ.ʃe/ | ^haspiréɔʃe |
| frwiktionary_ipa_mismatch | heu | noun | /ø/ | ^haspiréø |
| frwiktionary_ipa_mismatch | hum | interjection | /ɔm/ | ^haspiréœm; ^haspiréɔm |
| frwiktionary_ipa_mismatch | hurlement | noun | /yʁ.lə.mɑ̃/ | ^haspiréyʁləmɑ̃ |
| frwiktionary_ipa_mismatch | hache | noun | /aʃ/ | ^haspiréaʃ; ^haspiréaʃə; ynaʃ |
| frwiktionary_ipa_mismatch | hostilité | noun | /ɔs.ti.li.te/ | ^hmuetɔstilite |
| frwiktionary_ipa_mismatch | harem | noun | /a.ʁɛm/ | ^haspiréaʁɛm |
| frwiktionary_ipa_mismatch | hélicoptère | noun | /e.li.kɔp.tɛʁ/ | ^hmuetelikɔptɛʁ |


## 3. POS and gender

| Source | POS agreement / shared-word entries | Gender agreement / reference-gender entries |
|---|---|---|
| Lexique | 36692/38878 (94.38%) | 20806/21154 (98.35%) |
| French Wiktionary | 79099/81165 (97.45%) | 43471/45898 (94.71%) |

Lexique POS disagreements:

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| lexique_pos | ne | particle | particle | adverb |
| lexique_pos | un | noun | noun | article, numeral, pronoun |
| lexique_pos | tu | particle | particle | adjective, noun, pronoun, verb |
| lexique_pos | qui | conjunction | conjunction | pronoun |
| lexique_pos | qui | interjection | interjection | pronoun |
| lexique_pos | elle | noun | noun | pronoun |
| lexique_pos | mais | interjection | interjection | adverb, conjunction |
| lexique_pos | nous | noun | noun | pronoun |
| lexique_pos | CE | noun | noun | determiner, pronoun |
| lexique_pos | ce | article | article | determiner, pronoun |
| lexique_pos | avec | adverb | adverb | preposition |
| lexique_pos | que | conjunction | conjunction | pronoun |
| lexique_pos | voir | adverb | adverb | verb |
| lexique_pos | son | article | article | determiner, noun |
| lexique_pos | mon | article | article | determiner, pronoun |

Gender disagreements:

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| lexique_gender | Ami | noun | f | m |
| lexique_gender | médecin | noun |  | m |
| lexique_gender | pote | noun |  | m |
| lexique_gender | superbe | noun |  | f |
| lexique_gender | Angle | noun |  | m |
| lexique_gender | poète | noun |  | m |
| lexique_gender | Vierge | noun |  | f |
| lexique_gender | élan | noun |  | m |
| lexique_gender | maire | noun |  | m |
| lexique_gender | légume | noun |  | m |
| lexique_gender | Cancer | noun |  | m |
| lexique_gender | otage | noun |  | m |
| lexique_gender | poison | noun |  | m |
| lexique_gender | évêque | noun |  | m |
| lexique_gender | uni | noun | f | m |

French Wiktionary POS disagreements:

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| frwiktionary_pos | un | numeral | numeral | adjective, article, noun, pronoun |
| frwiktionary_pos | qui | conjunction | conjunction | pronoun |
| frwiktionary_pos | qui | interjection | interjection | pronoun |
| frwiktionary_pos | mais | interjection | interjection | adverb, conjunction, noun |
| frwiktionary_pos | ce | article | article | adjective, determiner, noun, pronoun, proper-noun |
| frwiktionary_pos | son | article | article | determiner, noun, proper-noun |
| frwiktionary_pos | mon | article | article | adverb, determiner, interjection, noun, proper-noun |
| frwiktionary_pos | comme | particle | particle | adverb, conjunction, verb |
| frwiktionary_pos | non | conjunction | conjunction | adverb, interjection, noun |
| frwiktionary_pos | sa | article | article | determiner, noun, proper-noun |
| frwiktionary_pos | ses | article | article | determiner, noun |
| frwiktionary_pos | oui | interjection | interjection | adverb, noun |
| frwiktionary_pos | si | interjection | interjection | adverb, conjunction, noun |
| frwiktionary_pos | deux | numeral | numeral | adjective, noun, proper-noun |
| frwiktionary_pos | votre | article | article | determiner |

Gender disagreements:

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| frwiktionary_gender | enfant | noun |  | f/m |
| frwiktionary_gender | Ami | noun | f | m |
| frwiktionary_gender | jeune | noun |  | f/m |
| frwiktionary_gender | malade | noun |  | f/m |
| frwiktionary_gender | garde | noun |  | f/m |
| frwiktionary_gender | médecin | noun |  | f/m |
| frwiktionary_gender | camarade | noun |  | f/m |
| frwiktionary_gender | gosse | noun |  | f/m |
| frwiktionary_gender | proche | noun |  | f/m |
| frwiktionary_gender | ministre | noun |  | f/m |
| frwiktionary_gender | pote | noun |  | f/m |
| frwiktionary_gender | élève | noun |  | f/m |
| frwiktionary_gender | môme | noun |  | f/m |
| frwiktionary_gender | artiste | noun |  | f/m |
| frwiktionary_gender | Russe | noun |  | f/m |


## 4. Headword coverage

Frequent Lexique lemmas present: 18274/19483 (93.79%). Our entry rows with a French Wiktionary word: 81165/88673 (91.53%).

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| missing_frequent_lemma | les |  | absent | freq=14662.3 |
| missing_frequent_lemma | l' |  | absent | freq=12746.8 |
| missing_frequent_lemma | d' |  | absent | freq=11876.4 |
| missing_frequent_lemma | des |  | absent | freq=10624.9 |
| missing_frequent_lemma | au |  | absent | freq=5322.5 |
| missing_frequent_lemma | ma |  | absent | freq=2346.9 |
| missing_frequent_lemma | cette |  | absent | freq=2320.68 |
| missing_frequent_lemma | aux |  | absent | freq=1907.57 |
| missing_frequent_lemma | ces |  | absent | freq=1547.5 |
| missing_frequent_lemma | leurs |  | absent | freq=886.55 |
| missing_frequent_lemma | quelques |  | absent | freq=732.57 |
| missing_frequent_lemma | vos |  | absent | freq=649.07 |
| missing_frequent_lemma | nos |  | absent | freq=579.19 |
| missing_frequent_lemma | eux |  | absent | freq=504.26 |
| missing_frequent_lemma | autres |  | absent | freq=375.14 |


## 5. Senses (top frequency entries)

Same word+POS: 4889/5000 (97.78%). Equal sense counts among shared pairs: 652/4889 (13.34%). Likely thin (ours=1, reference≥4): 906 (18.53% of shared pairs).

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| thin_entry | et | conjunction | 1 | 5 |
| thin_entry | avoir | noun | 1 | 4 |
| thin_entry | un | noun | 1 | 4 |
| thin_entry | du | article | 1 | 4 |
| thin_entry | mais | conjunction | 1 | 7 |
| thin_entry | plus | noun | 1 | 4 |
| thin_entry | tout | noun | 1 | 6 |
| thin_entry | tout | pronoun | 1 | 6 |
| thin_entry | moi | noun | 1 | 7 |
| thin_entry | non | adverb | 1 | 8 |
| thin_entry | non | noun | 1 | 5 |
| thin_entry | oui | adverb | 1 | 5 |
| thin_entry | si | noun | 1 | 11 |
| thin_entry | ici | adverb | 1 | 7 |
| thin_entry | chose | noun | 1 | 16 |

Other count disagreements:

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| top_sense_count | de | preposition | 8 | 58 |
| top_sense_count | être | noun | 2 | 4 |
| top_sense_count | être | verb | 6 | 12 |
| top_sense_count | la | noun | 1 | 3 |
| top_sense_count | ne | particle | 4 | 10 |
| top_sense_count | et | conjunction | 1 | 5 |
| top_sense_count | le | article | 4 | 8 |
| top_sense_count | à | preposition | 8 | 34 |
| top_sense_count | avoir | noun | 1 | 4 |
| top_sense_count | avoir | verb | 6 | 7 |
| top_sense_count | il | pronoun | 3 | 5 |
| top_sense_count | pas | adverb | 2 | 4 |
| top_sense_count | pas | noun | 3 | 17 |
| top_sense_count | un | article | 1 | 3 |
| top_sense_count | un | noun | 1 | 4 |


## 6. Examples

98163 / 111826 senses lack nonempty examples (87.78%); example coverage/agreement with the completeness goal: 12.22%. 80938 entries contain those gaps; 63511 have French Wiktionary examples at the same word+POS (78.47%), covering 79868 candidate senses (81.36% of missing senses). These are entry-level candidates, not aligned sense translations.

| Type | Word | POS | Ours | Reference |
|---|---|---|---|---|
| example_gap_with_source | être | noun | 2 senses without examples | French examples available at word+POS |
| example_gap_with_source | la | noun | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | je | pronoun | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | et | conjunction | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | avoir | noun | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | pas | noun | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | un | article | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | un | noun | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | un | pronoun | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | une | noun | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | tu | pronoun | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | en | preposition | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | aller | verb | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | elle | noun | 1 senses without examples | French examples available at word+POS |
| example_gap_with_source | dire | noun | 2 senses without examples | French examples available at word+POS |
