#!/bin/zsh
# Fill Persian meanings with Codex (gpt-6-luna, low) in N parallel shards. Ctrl-C stops all; rerun resumes.
# tools/fill-persian-codex.sh [shards=4] [total_limit=6000]
set -u
cd "${0:A:h}/.."
n=${1:-4}; total=${2:-6000}
mkdir -p dist/logs
trap 'kill 0' INT TERM
for i in $(seq 0 $((n - 1))); do
  python3 tools/fill_persian_v2.py dist/fr-v2.sqlite --model codex --batch-size 40 \
    --limit $((total / n)) --shard $i/$n > dist/logs/fill-$i.log 2>&1 &
done
print "running $n shards; progress: tail -n1 dist/logs/fill-*.log"
wait
print "done. Next: python3 tools/build.py --from-sqlite --db dist/fr-v2.sqlite"
