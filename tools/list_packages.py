#!/usr/bin/env python3
"""List workspace packages (used by CI matrices and the Makefile).

python tools/list_packages.py                 # JSON: [{"name","path","import_package","kind"}]
python tools/list_packages.py --import-packages   # space-separated import packages (for mypy -p)
python tools/list_packages.py --test-targets      # JSON list of package names that have tests
"""

import argparse
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def packages() -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    patterns = {
        "lib": "libs/*",
        "app": "apps/*",
        "service": "services/*/service",
        "contracts": "services/*/contracts",
    }
    for kind, pattern in patterns.items():
        for directory in sorted(ROOT.glob(pattern)):
            pyproject = directory / "pyproject.toml"
            if not pyproject.exists():
                continue
            data = tomllib.loads(pyproject.read_text())
            wheel = (
                data.get("tool", {})
                .get("hatch", {})
                .get("build", {})
                .get("targets", {})
                .get("wheel", {})
            )
            import_package = Path(wheel["packages"][0]).name if wheel.get("packages") else ""
            found.append(
                {
                    "name": data["project"]["name"],
                    "path": str(directory.relative_to(ROOT)),
                    "import_package": import_package,
                    "kind": kind,
                }
            )
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--import-packages", action="store_true")
    parser.add_argument("--test-targets", action="store_true")
    args = parser.parse_args()
    pkgs = packages()
    if args.import_packages:
        print(" ".join(p["import_package"] for p in pkgs if p["import_package"]))
    elif args.test_targets:
        print(
            json.dumps(
                [
                    {"name": p["name"], "path": p["path"]}
                    for p in pkgs
                    if (ROOT / p["path"] / "tests").exists()
                ]
            )
        )
    else:
        print(json.dumps(pkgs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
