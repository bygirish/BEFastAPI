"""The closed set of provider names. Config may only choose from these; metrics use them as label values (rule O-5).

Adding a vendor adapter (see docs/learning/phase-b): add its name here, implement a Sender in
infrastructure/providers/, register it in registry.py. A test keeps these three places in sync.
"""

PROVIDER_NAMES: frozenset[str] = frozenset({"console", "memory", "static", "smtp"})

# Adapters that exist for development/testing. They must never run in production (rule X-11).
DEV_ONLY_PROVIDERS: frozenset[str] = frozenset({"console", "memory", "static"})
