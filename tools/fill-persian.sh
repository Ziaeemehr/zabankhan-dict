#!/bin/zsh
# Fill Persian meanings a little at a time, then publish. Safe to stop (Ctrl-C) and rerun any time.
#   tools/fill-persian.sh [minutes]   (default 60)
set -u
DB=/Users/ziaee/git/zabankhan/content-tools/out/fr-dict.sqlite
cd "${0:A:h}/.."
started=0
if ! curl -sf http://127.0.0.1:8080/health >/dev/null; then zsh -ic 'llm-on' >/dev/null 2>&1; started=1
  until curl -sf http://127.0.0.1:8080/health >/dev/null; do sleep 5; done; fi
timeout $(( ${1:-60} * 60 )) python3 /Users/ziaee/git/zabankhan/content-tools/gen_persian_meanings.py "$DB" --limit 100000
[ $started = 1 ] && zsh -ic 'llm-off' >/dev/null 2>&1
python3 tools/publish.py "$DB" fr
git add -A && git commit -qm "Persian meanings: $(python3 -c "import json;print(json.load(open('fr/index.json'))['persian'])") entries" && git push -q
gh release upload fr-v1 dist/fr.sqlite --clobber
