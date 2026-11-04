"""MkDocs hooks for best-effort slide PDFs.

PDF generation is best-effort, but lecture pages always link to their PDFs.
When a PDF was not generated, MkDocs would report the missing target during a
strict build. Remove those links instead so the site stays buildable.
"""

from __future__ import annotations

import logging
import posixpath
import re
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

log = logging.getLogger("mkdocs.hooks.slides")

# `[PDF](../slides/<name>.pdf)` with an optional attr list and an optional
# preceding separator (` · `, spaces/tabs allowed around the middle dot).
_PDF_LINK = re.compile(
    r"(?:[ \t]*·[ \t]*)?\[PDF\]\((?P<href>\.\./slides/[^/)\s]+\.pdf)\)(?:\{[^}]*\})?"
)


def on_page_markdown(
    markdown: str, *, page: Page, config: MkDocsConfig, files: Files
) -> str:
    """Drop PDF links whose target does not exist in ``docs/slides/``."""
    if "slides/" not in markdown:
        return markdown

    docs_dir = Path(config.docs_dir)
    page_dir = posixpath.dirname(page.file.src_uri)

    def replace(match: re.Match[str]) -> str:
        href = match.group("href")
        target = docs_dir / posixpath.normpath(posixpath.join(page_dir, href))
        if target.is_file():
            return match.group(0)

        log.info("Skipping link to missing slide PDF: %s", href)
        return ""

    return _PDF_LINK.sub(replace, markdown)
