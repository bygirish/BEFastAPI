#!/usr/bin/env python3
"""Documentation health check (part of the Definition of Done, STANDARDS §11).

Checks, for README.md, CONTRIBUTING.md and everything under docs/:
  1. every relative Markdown link points at a file that exists, and `#anchors` match a real heading
  2. every path listed in the codebase map (docs/learning/kt/01-codebase-map.md) still exists
  3. every page under docs/learning/ is reachable from docs/learning/00-INDEX.md (no orphans)
  4. every *chapter* (docs/learning/phase-*/ and foundations/) has the standard sections
  5. optional --external: every http(s) link answers 200 (needs network)

    uv run python tools/check_docs.py
    uv run python tools/check_docs.py --external
"""

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEARNING = "docs/learning"
CHAPTER_DIRS = ("phase-", "foundations")
REQUIRED_CHAPTER_MARKERS = ("**Goal:**", "Interview Questions", "Self-check")
LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$", re.MULTILINE)
EXAMPLE_HOSTS = frozenset(
    {"example.com", "example.org", "example.net"}
)  # reserved for documentation (RFC 2606)
URL_RE = re.compile(r"https?://[^\s)>\"'`\]]+")


def strip_code(text: str) -> str:
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


def slugify(heading: str) -> str:
    """GitHub-style anchor: lowercase, drop punctuation/emoji, spaces -> hyphens."""
    heading = re.sub(r"`", "", heading).strip().lower()
    heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
    return heading.replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    text = FENCE_RE.sub("", path.read_text())
    seen: dict[str, int] = {}
    anchors: set[str] = set()
    for _, title in HEADING_RE.findall(text):
        slug = slugify(title)
        count = seen.get(slug, 0)
        anchors.add(slug if count == 0 else f"{slug}-{count}")
        seen[slug] = count + 1
    return anchors


def markdown_files(root: Path) -> list[Path]:
    files = [p for p in (root / "README.md", root / "CONTRIBUTING.md") if p.exists()]
    files += sorted((root / "docs").rglob("*.md"))
    return files


def check_links(root: Path, files: list[Path]) -> list[str]:
    errors: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}
    for md in files:
        text = strip_code(md.read_text())
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, anchor = target.partition("#")
            dest = md if not path_part else (md.parent / path_part).resolve()
            rel = md.relative_to(root)
            if not dest.exists():
                errors.append(f"{rel}: broken link -> {target}")
                continue
            if anchor and dest.suffix == ".md":
                anchors = anchor_cache.setdefault(dest, anchors_of(dest))
                if anchor not in anchors:
                    errors.append(
                        f"{rel}: anchor '#{anchor}' not found in {dest.relative_to(root)}"
                    )
    return errors


def check_codebase_map(root: Path) -> list[str]:
    map_file = root / LEARNING / "kt" / "01-codebase-map.md"
    if not map_file.exists():
        return []
    errors: list[str] = []
    for line in map_file.read_text().splitlines():
        match = re.match(r"^\|\s*`([^`|]+)`\s*\|", line)
        if not match:
            continue
        raw = match.group(1).strip()
        if any(
            token in raw for token in ("<", "*", "…", "{")
        ):  # placeholders / globs are documentation, not paths
            continue
        if not (root / raw).exists():
            errors.append(f"codebase map lists a path that does not exist: {raw}")
    return errors


def check_orphans(root: Path) -> list[str]:
    index = root / LEARNING / "00-INDEX.md"
    if not index.exists():
        return []
    linked: set[Path] = set()
    for target in LINK_RE.findall(strip_code(index.read_text())):
        if target.startswith(("http", "mailto")):
            continue
        linked.add((index.parent / target.partition("#")[0]).resolve())
    errors: list[str] = []
    for page in sorted((root / LEARNING).rglob("*.md")):
        if page.resolve() == index.resolve() or page.name == "chapter-template.md":
            continue
        if page.resolve() not in linked:
            errors.append(f"orphan page (not linked from 00-INDEX.md): {page.relative_to(root)}")
    return errors


def check_chapter_sections(root: Path) -> list[str]:
    errors: list[str] = []
    for page in sorted((root / LEARNING).rglob("*.md")):
        parent = page.parent.name
        if not parent.startswith(CHAPTER_DIRS):
            continue
        text = page.read_text()
        missing = [m for m in REQUIRED_CHAPTER_MARKERS if m not in text]
        if missing:
            errors.append(f"{page.relative_to(root)}: chapter is missing {missing}")
    return errors


def check_external(root: Path, files: list[Path]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for md in files:
        for url in URL_RE.findall(
            strip_code(md.read_text()) + "\n".join(FENCE_RE.findall(md.read_text()))
        ):
            url = url.rstrip(".,;")
            host = url.split("/")[2]
            if (
                "." not in host
                or host.startswith(("localhost", "127."))
                or host.endswith((".test", ".example", ".invalid"))
                or host in EXAMPLE_HOSTS
                or host.endswith(tuple(f".{h}" for h in EXAMPLE_HOSTS))
            ):
                continue  # sample data in docs, not a real link
            if url not in seen:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
                    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
                        seen[url] = str(resp.status)
                except urllib.error.HTTPError as exc:
                    seen[url] = str(exc.code)
                except Exception as exc:  # noqa: BLE001 - report, keep going
                    seen[url] = type(exc).__name__
            if seen[url] != "200":
                errors.append(f"{md.relative_to(root)}: {url} -> {seen[url]}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--external", action="store_true", help="also check http(s) links (needs network)"
    )
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root: Path = args.root

    files = markdown_files(root)
    errors = (
        check_links(root, files)
        + check_codebase_map(root)
        + check_orphans(root)
        + check_chapter_sections(root)
    )
    if args.external:
        errors += check_external(root, files)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(
        f"Checked {len(files)} Markdown file(s): {'OK' if not errors else f'{len(errors)} problem(s)'}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
