#!/usr/bin/env python3
"""Export the offline dictionary SQLite into small JSON shards for GitHub Pages.

    python3 tools/publish.py SRC.sqlite LANG     # writes LANG/<key>.json, LANG/index.json, copies LANG.sqlite to dist/
Shard key = first two letters of the first word, accents removed, lowercase ("_" when not a-z).
The app downloads only the shard it needs; the full SQLite goes to a Release for offline use.
"""
import json, os, shutil, sqlite3, sys, unicodedata, time

def key(word):
    first = word.split()[0] if word.split() else word
    s = "".join(c for c in unicodedata.normalize("NFD", first.lower()) if not unicodedata.combining(c))
    s = "".join(c if "a" <= c <= "z" else "_" for c in s[:2])
    return s.ljust(2, "_")

def main():
    src, lang = sys.argv[1], sys.argv[2]
    db = sqlite3.connect(src)
    cols = ["word", "pos", "rank", "ipa", "gender", "en", "example", "forms", "fa"]
    # Older databases predate monolingual definitions.
    if "french_definitions" in {r[1] for r in db.execute("PRAGMA table_info(entry)")}:
        cols.append("french_definitions")
    shards = {}
    for row in db.execute(f"SELECT {', '.join(cols)} FROM entry ORDER BY rank"):
        e = dict(zip(cols, row))
        e["en"] = json.loads(e["en"]) if e["en"] else []
        e["french_definitions"] = json.loads(e["french_definitions"]) if e.get("french_definitions") else []
        e = {k: v for k, v in e.items() if v not in ("", [], None)}
        shards.setdefault(key(e["word"]), []).append(e)
    shutil.rmtree(lang, ignore_errors=True); os.makedirs(lang)
    for k, entries in shards.items():
        with open(f"{lang}/{k}.json", "w") as f:
            json.dump(entries, f, ensure_ascii=False, separators=(",", ":"))
    fa = db.execute("SELECT count(*) FROM entry WHERE fa != ''").fetchone()[0]
    total = db.execute("SELECT count(*) FROM entry").fetchone()[0]
    meta = dict(db.execute("SELECT key, value FROM meta").fetchall()) if db.execute(
        "SELECT name FROM sqlite_master WHERE name='meta'").fetchone() else {}
    with open(f"{lang}/index.json", "w") as f:
        json.dump({"lang": lang, "format": 1, "version": int(time.time()), "entries": total, "persian": fa,
                   "shards": sorted(shards), "sources": meta.get("sources", "")}, f, ensure_ascii=False)
    os.makedirs("dist", exist_ok=True); shutil.copy(src, f"dist/{lang}.sqlite")
    print(f"{lang}: {total} entries, {fa} with Persian, {len(shards)} shards")

if __name__ == "__main__":
    main()
