# Zabankhan dictionary v2

Goal: a clean, ad-free learner's dictionary that is the app's default lookup, online by default and fully downloadable for offline use. Persian meanings fill in over time.

## What v1 lacks

- Inflected words do not resolve: `prends`, `belle`, `allées` find nothing.
- Senses are flattened into one gloss list; examples, register tags and synonyms are lost (one example per entry, 9% coverage).
- Reflexive and multi-word entries (`se rendre compte`) are hard to reach from text.
- No link from a word to its expressions (`prendre` → `prendre feu`, `prendre le temps`).
- Verb tables exist for 8% of entries; adjectives have no feminine/plural forms.

## Data format 2

Built by `tools/build.py` from English Wiktionary (kaikki.org) and Lexique 3.83. Published to GitHub Pages under `<lang>/v2/`.

Expanded logical view of a shard (the compact wire layouts are specified below). Keys start with two characters and follow the exact split rule below:

```json
{
  "entries": [{
    "id": 1234, "word": "prendre", "pos": "verb", "freq": 5,
    "ipa": "/pʁɑ̃dʁ/", "gender": "", "audio": "",
    "senses": [
      {"en": "to take", "fa": "", "tags": ["transitive"],
       "examples": [{"text": "prends ma main", "en": "take my hand", "fa": ""}],
       "synonyms": ["saisir"]}
    ],
    "forms": {"present": ["prends", "prends", "prend", "prenons", "prenez", "prennent"], "past_participle": "pris"},
    "expressions": ["prendre feu", "prendre le temps"]
  }],
  "redirects": {"prends": [[1234, "imp.2s;ind.pres.1s,2s"]]},
  "targets": {"1234": ["prendre", "verb"]}
}
```

- `freq`: 1–5 band from Lexique frequency (5 = most common); 0 when unknown.
- `senses`: at most 8 per entry, at most 2 examples per sense; tags limited to learner-relevant ones (informal, formal, slang, figurative, dated, rare, vulgar, derogatory, transitive, intransitive, pronominal, uncountable, plural-only, Quebec, Belgium, Switzerland).
- `forms`: verbs: infinitive, present/imperfect/future/conditional/subjunctive (6 persons), past participle, present participle, auxiliary. Adjectives: masculine, feminine, masculine plural, feminine plural. Nouns: plural, feminine counterpart.
- `redirects`: every inflected form found in form-of senses and `forms`, keyed by the normalized form, stored in the shard of the form (not the lemma).
- Single-word forms redirect only to single-word lemmas or a bare reflexive verb (`se prendre`, `s'abstenir`). Longer expressions are reached through `expressions` and idiom matching. Multiword forms may redirect to multiword lemmas.
- `expressions`: at most 30 unique headwords, ordered by vulgar/derogatory last, word count ascending, rarest word's Lexique frequency descending (unknown = 0), then alphabetical. Words are Unicode letter runs, splitting apostrophes and punctuation; frequency is the maximum lemma film + book frequency.
- Entries with only form-of senses are dropped (they become redirects).

`<lang>/v2/index.json`: `{lang, format: 2, version, entries, persian, shards, sources}`.

`<lang>/v2/<lang>.sqlite` in the GitHub release for full offline download (tables `entry`, `sense`, `example`, `redirect`).

v1 files stay online until the app version that reads v2 is installed everywhere.

## Persian

`fa` per sense and per example. `tools/fill-persian.sh` fills them in over time with the local model, most frequent entries first, and republishes. The app translates missing senses on demand with the user's model or Google and caches them on the device, marked with the source icon.

## App

Lookup order for a tapped word: exact headword, redirect (inflection to lemma), lemma lexicon, idioms that cover the tapped word in its sentence. A short line says how the form was resolved ("prends → prendre, present").

Entry view, minimal and readable:

- Header: headword, IPA, listen button, part-of-speech and gender chips, frequency dots.
- Numbered senses: meaning in the meaning language (Persian or English) with source icon, register tags as small labels, examples with their translation (listen on tap), synonyms as tappable words.
- Save picks the sense: "Add to Leitner" saves the word with the chosen sense's meaning and example.
- "Expressions with prendre": tappable list that opens each expression.
- Forms: verbs as a compact conjugation table (tenses as a dropdown, never a horizontal scroller); adjectives and nouns as one line.
- Web dictionaries remain available below as a secondary option.

Also a standalone dictionary screen with a search box (prefix search inside the downloaded or cached shards).

## Tests

Build script: unit tests for redirects (`prends`, `belle`, `allées`, `yeux`), reflexives, expression links, tag filtering, shard key.
App: lookup of inflected forms, reflexives in context, idiom inside a sentence, offline vs online parity, sense-specific save.

## Redirect form codes

Labels use dots between components and semicolons between analyses. Identical
analyses are deduplicated per lemma and POS; persons sharing a prefix use commas
(`ind.pres.1s,2s`). Form-of chains combine grammatical tags, e.g. `pp.f.pl`.

| Code | Meaning |
| --- | --- |
| ind, subj, cond, imp | indicative, subjunctive, conditional, imperative |
| pres, impf, fut, past | present, imperfect, future, past |
| pp, ppr, inf | past participle, present participle, infinitive |
| 1s, 2s, 3s, 1p, 2p, 3p | person and singular/plural |
| 1, 2, 3 | person when number is unspecified |
| m, f | masculine, feminine |
| sg, pl | singular, plural (without a person) |
| refl, form | reflexive link, otherwise unspecified form |

## Exact shard lookup rule

Use `lookup_shard_key(word, index)` in `tools/build.py` as the reference.
Collapse whitespace and trim, replace curly apostrophe `’` with ASCII `'`,
normalize NFC and lowercase. Take only the first whitespace-separated token.
Decompose it with NFD and remove combining characters. Take the first two
characters, replace each character outside ASCII `a`–`z` with `_`, and pad on
the right with `_` to width two. If this key is a property of `index.split`,
increase the width by one and repeat until the key is absent from `index.split`, including for short tokens. Do not
select the first child or transliterate ligatures: `œ` becomes `_`. A computed
key absent from `index.shards` means no results.

For split parents `se`, `de`, `a_`, `_i`, lookup gives `se rendre compte` →
`se_`, `des` → `des`, `désormais` → `des`, `à` → `a__`, `œil` → `_il`.
Without the corresponding split parent, use `se`, `de`, `de`, `a_`, `_i`.
The builder recursively splits shards exceeding 999,999 bytes, increasing the
prefix width by one each time, and refuses to publish an indivisible oversized shard.

## Compact wire encoding

SQLite retains full named columns. JSON redirects use `[entry_id, form_label_index]`;
each shard's `targets` maps those IDs (JSON string keys) to `[lemma, pos]`.
Resolve the lemma's shard with the same lookup helper, then select its entry ID.
Positional records retain empty defaults. `audio` is either an empty string or
`[prefix_index, filename]`; concatenate `index.audio_prefixes[prefix_index]`
and filename to recover the original URL. The positional record layouts below define the wire format.

On the wire, each sense is `[en, fa, tags, synonyms, examples]` and each
example is `[text, en, fa]`, with empty values retained in their positions.
The expanded sense/example objects above illustrate their semantic fields.

Entries on the wire are positional arrays in this order:
`[id, word, pos, freq, ipa, gender, audio, senses, forms, expressions, more_examples]`.
Redirects use `[entry_id, form_label_index]`; the second number indexes the
shard's `form_labels` array of compact code strings. The expanded example above
shows semantic fields; these positional layouts are the actual wire encoding.
When every sense lacks an example, `more_examples` contains up to three French-only
strings from matching French Wiktionary word+POS examples (20–160 characters).
Readers should accept entries without candidates. The source list credits
`French Wiktionary (CC BY-SA 4.0)`.
