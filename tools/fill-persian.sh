#!/bin/zsh
# Fill v2 translations locally, then regenerate shards. No publication.
# tools/fill-persian.sh [minutes] (default 60)
set -u
cd "${0:A:h}/.."
DB="$PWD/dist/fr-v2.sqlite"
[[ -f "$DB" ]] || { print -u2 "Build the v2 database first: python3 tools/build.py"; exit 1; }
started=0
cleanup() {
  if [[ $started = 1 ]]; then zsh -ic 'llm-off' >/dev/null 2>&1; fi
}
trap cleanup EXIT
if ! curl -sf http://127.0.0.1:8080/health >/dev/null; then
  zsh -ic 'llm-on' >/dev/null 2>&1 || exit 1
  started=1
  ready=0
  for attempt in {1..120}; do
    if curl -sf http://127.0.0.1:8080/health >/dev/null; then ready=1; break; fi
    sleep 5
  done
  [[ $ready = 1 ]] || { print -u2 'Local model did not become ready.'; exit 1; }
fi
python3 tools/fill_persian_v2.py "$DB" --limit 100000 --minutes "${1:-60}"
fill_status=$?
python3 tools/build.py --from-sqlite --db "$DB" || exit $?
exit $fill_status
