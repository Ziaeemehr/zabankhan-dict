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

Shard `<lang>/v2/<key>.json` (key = first two letters of the first word, accents removed, as in v1):

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
  "redirects": {"prends": [{"lemma": "prendre", "pos": "verb", "form": "present 1s/2s, imperative 2s"}]}
}
```

- `freq`: 1–5 band from Lexique frequency (5 = most common); 0 when unknown.
- `senses`: at most 8 per entry, at most 2 examples per sense; tags limited to learner-relevant ones (informal, formal, slang, figurative, dated, rare, vulgar, transitive, intransitive, pronominal, uncountable, plural-only, Quebec, Belgium, Switzerland).
- `forms`: verbs: infinitive, present/imperfect/future/conditional/subjunctive (6 persons), past participle, present participle, auxiliary. Adjectives: masculine, feminine, masculine plural, feminine plural. Nouns: plural, feminine counterpart.
- `redirects`: every inflected form found in form-of senses and `forms`, keyed by the normalized form, stored in the shard of the form (not the lemma).
- Reflexive headwords (`se rendre compte`, `s'en aller`) are also reachable from the verb without `se` and from conjugated text through redirects plus idiom matching.
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
