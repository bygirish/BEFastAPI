#!/usr/bin/env python3
"""Scaffold a new service: services/<name> (+ contracts, migrations, observability, tests)
and apps/<name>_api (standalone entrypoint), then re-sync workspace registrations.

    uv run python tools/new_service.py notifications
    uv run python tools/new_service.py notifications --dry-run

Names: lowercase letters/digits, starting with a letter (they appear in event names and prefixes).
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import sync_workspace

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = Path(__file__).resolve().parent / "templates"
NAME_RE = re.compile(r"^[a-z][a-z0-9]{1,23}$")
RESERVED = {
    "platform",
    "monolith",
    "tools",
    "libs",
    "apps",
    "services",
    "internal",
    "api",
    "health",
    "admin_",
}


def tokens(name: str) -> dict[str, str]:
    return {"{{service}}": name, "{{Service}}": name.capitalize(), "{{SERVICE}}": name.upper()}


def render_tree(
    template_dir: Path, target: Path, mapping: dict[str, str], *, dry_run: bool
) -> list[Path]:
    written: list[Path] = []
    for source in sorted(p for p in template_dir.rglob("*") if p.is_file()):
        relative = source.relative_to(template_dir)
        parts = [part.replace("__service__", mapping["{{service}}"]) for part in relative.parts]
        parts[-1] = parts[-1].removesuffix(".tmpl")
        destination = target.joinpath(*parts)
        content = source.read_text()
        for token, value in mapping.items():
            content = content.replace(token, value)
        if "{{" in content and not destination.name.endswith(".mako"):
            leftover = re.findall(r"\{\{[A-Za-z_]+\}\}", content)
            if leftover:
                raise SystemExit(f"Unresolved template tokens {leftover} in {source}")
        written.append(destination)
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)
    return written


def format_generated(paths: list[Path]) -> None:
    """Best effort: make generated code pass `ruff format --check` / import sorting from day one."""
    ruff = shutil.which("ruff") or str(ROOT / ".venv" / "bin" / "ruff")
    if not Path(ruff).exists():
        print("ruff not found; run `make format` before committing", file=sys.stderr)
        return
    targets = [str(p) for p in paths]
    subprocess.run(
        [ruff, "check", "--fix", "--quiet", "--select", "I,RUF022", *targets], check=False, cwd=ROOT
    )
    subprocess.run([ruff, "format", "--quiet", *targets], check=False, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("name")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    name: str = args.name

    if not NAME_RE.match(name) or name in RESERVED:
        print(
            f"Invalid or reserved service name {name!r}: use [a-z][a-z0-9]{{1,23}}", file=sys.stderr
        )
        return 2
    service_dir, app_dir = ROOT / "services" / name, ROOT / "apps" / f"{name}_api"
    if (service_dir / "pyproject.toml").exists() or app_dir.exists():
        print(f"Service {name!r} already exists", file=sys.stderr)
        return 2

    mapping = tokens(name)
    files = render_tree(TEMPLATES / "service", service_dir, mapping, dry_run=args.dry_run)
    files += render_tree(TEMPLATES / "standalone_app", app_dir, mapping, dry_run=args.dry_run)
    print(
        f"{'Would create' if args.dry_run else 'Created'} {len(files)} files for service '{name}'"
    )
    if args.dry_run:
        for f in files:
            print("  ", f.relative_to(ROOT))
        return 0

    sync_workspace.sync(ROOT, check=False)
    format_generated([service_dir, app_dir])
    print(
        f"""
Next steps
  1. uv sync --all-packages
  2. uv run pytest services/{name} -q
  3. Add it to docs/architecture/ARCHITECTURE.md §5 (owner, owns, exposes, depends on)
  4. Replace the SAMPLE ping flow with real use cases (contracts first)
"""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
