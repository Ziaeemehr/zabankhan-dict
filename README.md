# zabankhan-dict

Dictionary data for the Zabankhan reading app.

- `fr/<key>.json`: French entries, sharded by the first two letters of the headword (accents removed). `fr/index.json` lists the shards and the build version.
- The full SQLite file for offline use is attached to each Release.
- Persian meanings (`fa`) are filled in over time.

Sources: English Wiktionary via kaikki.org and Lexique 3.83, both CC BY-SA 4.0. This data is shared under CC BY-SA 4.0.

## Word families

Download [Démonette-2.0's relations.csv](https://osf.io/download/8qcsw/) and pass it to the v2 build.

```sh
python3 tools/build.py --demonette /path/to/relations.csv
# To update an existing v2 database and re-export its shards:
python3 tools/build.py --from-sqlite --demonette /path/to/relations.csv
```

The build matches spellings and parts of speech, keeps documented derivational
links, and selects up to eight relatives per part of speech by Lexique
frequency. Common learner-facing families for *apprendre* and *comprendre* are
also curated so their frequently used forms remain discoverable. It includes
the queried headword in its family. The SQLite
`entry.word_family` column and optional 13th field of a v2 JSON entry hold the
same list of lemma and part-of-speech pairs. Definitions stay in the target
entries.

Word-family data is adapted from Démonette-2 by Fiammetta Namer, Nabil Hathout
and colleagues, Demonext (ANR-17-CE23-0005), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
[Dataset](https://doi.org/10.17605/OSF.IO/DB2W8) · [Publication](https://www.peren-revues.fr/lexique/1242).
The `calmement` example also uses the documented family in French Wiktionary
([calmement](https://fr.wiktionary.org/wiki/calmement) and
[calme](https://fr.wiktionary.org/wiki/calme), CC BY-SA 4.0).
