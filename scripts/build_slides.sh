#!/usr/bin/env bash
# Build Marp decks from slides/*.md into docs/slides/.
# HTML is required; PDF is best-effort (a missing browser must not fail the build).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="$ROOT/docs/slides"
mkdir -p "$OUT"

# Marp writes HTML into docs/slides/, while the decks reference assets/
# relative to slides/. Mirror the asset directories next to the generated files.
for src in "$ROOT/slides/assets" "$ROOT/slides/tikz" "$ROOT"/slides/Лекция*_figs; do
  if [[ ! -d "$src" ]]; then
    continue
  fi
  asset_dir="$(basename "$src")"
  rm -rf "$OUT/$asset_dir"
  cp -a "$src" "$OUT/"
done

if [[ -x "$ROOT/node_modules/.bin/marp" ]]; then
  MARP=("$ROOT/node_modules/.bin/marp")
else
  MARP=(npx --yes @marp-team/marp-cli)
fi

failures=0
pdf_failures=()

for src in "$ROOT"/slides/lecture-*.md; do
  [[ -e "$src" ]] || continue
  name="$(basename "$src" .md)"

  if ! "${MARP[@]}" --html --allow-local-files "$src" -o "$OUT/$name.html"; then
    echo "ERROR: HTML build failed for $name" >&2
    failures=$((failures + 1))
    continue
  fi
  echo "built $name.html"

  if ! "${MARP[@]}" --html --pdf --allow-local-files "$src" -o "$OUT/$name.pdf"; then
    echo "WARNING: PDF build failed for $name (no browser or PDF engine?)" >&2
    pdf_failures+=("$name")
  else
    echo "built $name.pdf"
  fi
done

if ((${#pdf_failures[@]})); then
  printf 'WARNING: PDF not built for: %s\n' "${pdf_failures[*]}" >&2
fi

((failures == 0)) || exit 1
exit 0
