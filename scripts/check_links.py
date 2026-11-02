#!/usr/bin/env python3
"""Check internal links and asset references in the built MkDocs site."""

from __future__ import annotations

import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SKIP_SCHEMES = {"http", "https", "mailto", "tel", "javascript", "data"}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.links.append(value)


def site_prefix() -> str:
    """Return the deployment path from site_url, e.g. /dde-course."""
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    match = re.search(r"^site_url:\s*(\S+)\s*$", config, flags=re.MULTILINE)
    if not match:
        return ""
    return urlparse(match.group(1)).path.rstrip("/")


def is_external(value: str) -> bool:
    value = value.strip()
    if not value or value.startswith("#") or value.startswith("//"):
        return True
    parsed = urlparse(value)
    return parsed.scheme.lower() in SKIP_SCHEMES


def resolve(page: Path, raw: str, prefix: str) -> Path | None:
    value = html.unescape(raw.strip())
    if is_external(value):
        return None

    parsed = urlparse(value)
    path = unquote(parsed.path)
    if not path:
        return None

    if path.startswith("/"):
        if prefix and (path == prefix or path.startswith(prefix + "/")):
            path = path[len(prefix):] or "/"
        candidate = SITE / path.lstrip("/")
    else:
        candidate = page.parent / path

    candidate = candidate.resolve()
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def check_page(page: Path, prefix: str) -> list[tuple[Path, str, Path]]:
    parser = LinkParser()
    parser.feed(page.read_text(encoding="utf-8", errors="ignore"))

    broken: list[tuple[Path, str, Path]] = []
    for raw in parser.links:
        target = resolve(page, raw, prefix)
        if target is None:
            continue
        try:
            target.relative_to(SITE.resolve())
        except ValueError:
            broken.append((page, raw, target))
            continue
        if not target.is_file():
            broken.append((page, raw, target))
    return broken


def main() -> int:
    if not SITE.is_dir():
        print(f"ERROR: {SITE} not found; run mkdocs build first", file=sys.stderr)
        return 1

    prefix = site_prefix()
    pages = sorted(SITE.rglob("*.html"))
    broken: list[tuple[Path, str, Path]] = []

    for page in pages:
        broken.extend(check_page(page, prefix))

    if broken:
        print(f"Broken internal links: {len(broken)}", file=sys.stderr)
        for page, raw, target in broken:
            print(f"  {page.relative_to(SITE)}: {raw} -> {target}", file=sys.stderr)
        return 1

    print(f"internal links: OK ({len(pages)} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
