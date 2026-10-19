from pathlib import Path

import check_docs as cd

GOOD_CHAPTER = "# T\n\n**Goal:** x\n\n## 🎯 Interview Questions\n\n## ✅ Self-check\n"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_slugify_matches_github_style() -> None:
    assert (
        cd.slugify("Phase A1 — Foundation (what exists today)")
        == "phase-a1--foundation-what-exists-today"
    )
    assert (
        cd.slugify("🎯 Interview Questions") == "-interview-questions"
    )  # GitHub keeps the leading hyphen
    assert cd.slugify("2.1 The problem") == "21-the-problem"


def test_detects_broken_file_and_anchor_links(tmp_path: Path) -> None:
    write(
        tmp_path,
        "README.md",
        "[ok](docs/a.md#real-heading) [bad](docs/missing.md) [badanchor](docs/a.md#nope)\n",
    )
    write(tmp_path, "docs/a.md", "# Title\n\n## Real heading\n")
    errors = cd.check_links(tmp_path, cd.markdown_files(tmp_path))
    assert any("missing.md" in e for e in errors)
    assert any("#nope" in e for e in errors)
    assert not any("real-heading" in e for e in errors)


def test_links_inside_code_are_ignored(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "```\n[x](nope.md)\n```\nand `[y](nope2.md)`\n")
    assert cd.check_links(tmp_path, cd.markdown_files(tmp_path)) == []


def test_codebase_map_paths_must_exist(tmp_path: Path) -> None:
    (tmp_path / "libs").mkdir()
    write(
        tmp_path,
        "docs/learning/kt/01-codebase-map.md",
        "| `libs` | ok |\n| `libs/ghost` | gone |\n| `services/<name>/x` | placeholder |\n",
    )
    errors = cd.check_codebase_map(tmp_path)
    assert errors == ["codebase map lists a path that does not exist: libs/ghost"]


def test_orphans_and_chapter_sections(tmp_path: Path) -> None:
    write(tmp_path, "docs/learning/00-INDEX.md", "[c](phase-x/01.md)\n")
    write(tmp_path, "docs/learning/phase-x/01.md", GOOD_CHAPTER)
    write(tmp_path, "docs/learning/phase-x/02.md", "# no sections here\n")
    write(tmp_path, "docs/learning/glossary.md", "# g\n")
    orphans = cd.check_orphans(tmp_path)
    assert any("02.md" in e for e in orphans) and any("glossary.md" in e for e in orphans)
    assert not any("01.md" in e for e in orphans)
    sections = cd.check_chapter_sections(tmp_path)
    assert len(sections) == 1 and "02.md" in sections[0]


def test_real_repository_docs_are_healthy() -> None:
    """The repository's own docs must always pass (this is the guard that keeps them honest)."""
    root = cd.ROOT
    files = cd.markdown_files(root)
    problems = (
        cd.check_links(root, files)
        + cd.check_codebase_map(root)
        + cd.check_orphans(root)
        + cd.check_chapter_sections(root)
    )
    assert problems == []
