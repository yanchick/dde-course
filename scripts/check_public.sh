#!/usr/bin/env bash
# Guard against publishing reference solutions and local filesystem paths.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

status=0

fail() {
  echo "ERROR: $*" >&2
  status=1
}

tracked_solutions="$(git ls-files | grep -E '(^|/)эталон[^/]*\.py$' || true)"
if [[ -n "$tracked_solutions" ]]; then
  fail "reference solution files are tracked by git:"
  printf '%s\n' "$tracked_solutions" >&2
fi

tracked_instructor="$(git ls-files | grep '^instructor/solutions/' || true)"
if [[ -n "$tracked_instructor" ]]; then
  fail "instructor/solutions must not be tracked by git:"
  printf '%s\n' "$tracked_instructor" >&2
fi

tracked_materials="$(git ls-files | grep '^materials/' || true)"
if [[ -n "$tracked_materials" ]]; then
  fail "materials/ is a local archive and must not be tracked by git:"
  printf '%s\n' "$tracked_materials" >&2
fi

solution_paths="$(find docs code slides -name 'эталон*' -print 2>/dev/null || true)"
if [[ -n "$solution_paths" ]]; then
  fail "reference solution paths found in published directories:"
  printf '%s\n' "$solution_paths" >&2
fi

absolute_paths="$(grep -RIn --include='*.md' --include='*.py' --include='*.yml' --include='*.html' \
  -E 'ИТМО/ДДЕ|/home/[^/]+/Yandex' docs code slides 2>/dev/null || true)"
if [[ -n "$absolute_paths" ]]; then
  fail "absolute vault paths found in published content:"
  printf '%s\n' "$absolute_paths" >&2
fi

if ((status == 0)); then
  echo "public content check: OK"
fi
exit "$status"
