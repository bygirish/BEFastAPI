# 02 · Monorepo & uv: how the pieces are packaged

**Goal:** understand Python packaging well enough to read any `pyproject.toml` in this repo and know *why* it looks the way it does.
**Prerequisites:** chapter 01. **Time:** 45 min.

---

## 2.1 Python packaging in five minutes

| Idea | Meaning | Where you see it |
|---|---|---|
| **Module / package** | A `.py` file / a folder of them you can `import` | `platform_core/` |
| **Distribution** | A *named, versioned* bundle you can install (`pip install platform-core`) | `name = "platform-core"` |
| **`pyproject.toml`** | Declares a distribution: name, version, dependencies, build tool, tool settings | one per package |
| **Virtual environment** | A private folder of installed packages for this project | `.venv/` |
| **Build backend** | Turns source into an installable wheel (we use *hatchling*) | `[build-system]` |
| **Editable install** | The venv points at your source, so edits are live | how workspace members are installed |

> ⚠️ **Trap — package name ≠ import name.** The distribution is `platform-core` (hyphen) but you `import platform_core`
> (underscore). Dependencies are always written with the *distribution* name.

### The `src/` layout

```
libs/platform_core/
├── pyproject.toml
├── src/platform_core/      ← the importable package lives under src/
│   └── __init__.py
└── tests/
```

> 💡 **Learning Thought — why `src/`?** If code sits next to the tests, `import platform_core` can accidentally pick up the *folder*
> instead of the *installed* package, hiding packaging mistakes (missing files, wrong dependencies). With `src/`, a test can only import what
> was really installed — so a green test means the package is genuinely importable.

## 2.2 Anatomy of one package

`libs/platform_events/pyproject.toml` (abridged):

```toml
[project]
name = "platform-events"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "platform-core",            # a sibling package in this repo
    "platform-observability",   # another sibling
    "pydantic>=2.7",            # a normal PyPI package
    "sqlalchemy[asyncio]>=2.0.30",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/platform_events"]

[tool.uv.sources]
platform-core = { workspace = true }          # "resolve this name from THIS repo, not PyPI"
platform-observability = { workspace = true }

[dependency-groups]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "aiosqlite>=0.20"]   # only needed to test THIS package
```

Read it top to bottom: *what am I → what do I need → how am I built → where do my siblings come from → what do my tests need.*

> 💡 **Learning Thought — a package declares its own real dependencies.** `platform-events` lists `pydantic` even if its neighbour also
> does. This is rule **B-7** and is what makes a package liftable into another repo: copy the folder, and everything it needs is written down.

## 2.3 The uv workspace

**uv** is a fast tool that creates the venv, resolves versions, installs and runs commands. A **workspace** lets many packages share
one venv and one lockfile.

The root `pyproject.toml`:

```toml
[tool.uv.workspace]
members = [
    "libs/*",
    "apps/*",
    # >>> generated:workspace-members (tools/sync_workspace.py)
    # <<< generated:workspace-members          ← service entries are written here by the generator
]
```

▶ **Try it**
```bash
uv sync --all-packages        # create .venv and install every member (editable) + dev tools
uv run python tools/list_packages.py
```
Output (abridged — one object per package):
```json
[
  {
    "name": "platform-core",
    "path": "libs/platform_core",
    "import_package": "platform_core",
    "kind": "lib"
  },
  ...
]
```

### Lockfile
`uv.lock` records the exact version of every dependency. **Commit it.** It is why "works on my machine" also means "works in CI".

### Run one package alone (rule B-6)
```bash
uv run --isolated --package platform-core pytest libs/platform_core -q
```
`--package` + `--isolated` builds a throw-away environment containing **only that package's dependency closure**. If its tests pass there,
it does not secretly rely on a sibling. CI runs every package this way.

## 2.4 Why `service/` and `contracts/` are siblings (not nested)

We wanted `services/auth/pyproject.toml` with `services/auth/contracts/` inside it. uv refused:

```
DEBUG Project is contained in non-workspace project: .../services/demo
error: Failed to build `demo-contracts` ... `platform-core` references a workspace ..., but is not a workspace member
```

A workspace member may not live inside *another member's* folder. So each service is **two sibling packages** under a plain folder:

```
services/auth/
├── contracts/pyproject.toml   → auth-contracts   (public)
└── service/pyproject.toml     → auth-service     (private)
```

> 💡 **Learning Thought — the tool pushed us into a better design.** The public/private split is now visible in the folder tree itself,
> and a consumer can depend on `auth-contracts` without ever installing `auth-service`.

## 2.5 Entry points — how the monolith finds services without importing them

If `monolith_app` did `from auth_service import …`, every new service would mean editing shared code. Instead each service announces
itself in its own `pyproject.toml`:

```toml
[project.entry-points."befastapi.services"]
auth = "auth_service.module:build_module"
```

At start-up, `platform_http.load_modules()` asks Python's package metadata "who registered under `befastapi.services`?", imports each
`build_module`, and calls it.

▶ **Try it** (after generating a service in chapter 07):
```python
from importlib.metadata import entry_points
print([ep.name for ep in entry_points(group="befastapi.services")])   # ['notes']
```

> 💡 **Learning Thought — discovery beats registration.** Adding a service never edits `libs/` or `apps/monolith`; installing it is enough.

## 2.6 Generated blocks

Three files contain machine-written sections (`tools/sync_workspace.py`): the workspace member list, the monolith's service dependencies,
and `.importlinter`. CI runs `sync_workspace.py --check` so nobody forgets to regenerate.

> ⚠️ **Trap — editing between the `>>> generated` / `<<< generated` markers.** Your change will be overwritten by the next sync. Edit the
> generator instead.

## 🧪 Lab 2.1 — read a pyproject
Open `apps/monolith/pyproject.toml`. Answer: (a) which packages does the monolith depend on directly? (b) why are services *not*
listed by hand? (c) what does `{ workspace = true }` mean?
<details><summary>Solution</summary>

(a) the five `platform-*` libs plus fastapi/uvicorn, and (once any exist) every `<name>-service` inside the generated block.
(b) the block is generated from the services on disk by `tools/sync_workspace.py`, so it cannot drift. (c) "take this dependency from this
repo's workspace, not from PyPI".
</details>

## 🎯 Interview Questions
1. **Why a workspace instead of one big package?** *Each unit declares its own dependencies and can be tested alone and lifted out. One
   lockfile still guarantees consistent versions.*
2. **What is an entry point and why use one here?** *A named hook in installed-package metadata. It lets the monolith discover services
   dynamically, so adding a service doesn't edit shared code.*
3. **What does a lockfile give you that `>=` ranges don't?** *Reproducibility — exact versions, so CI and teammates run identical code.*
4. **Why `src/` layout?** *Tests import the installed package, not the local folder, which exposes packaging errors early.*

## ✅ Self-check
- [ ] I can explain package name vs import name.
- [ ] I know what `uv sync --all-packages` and `uv run --isolated --package X` do differently.
- [ ] I can explain why a member can't be nested inside another member.
- [ ] I know which files are generated and must not be hand-edited.

## 📚 Further reading
- uv — Workspaces: <https://docs.astral.sh/uv/concepts/projects/workspaces/>
- Python Packaging — Entry points specification: <https://packaging.python.org/en/latest/specifications/entry-points/>
- Python Packaging User Guide — *src layout vs flat layout*: <https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/>

**Next:** [03 · Boundaries, contracts & layers →](03-boundaries-contracts-and-layers.md)
