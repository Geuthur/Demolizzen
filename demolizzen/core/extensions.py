"""Which modules the bot loads at start."""

# Standard Library
import re

# The setting that names further modules, see .env.example.
SETTING = "EXTRA_EXTENSIONS"


def with_extra(standard: list[str], extra: str | None) -> list[str]:
    """The modules to load: the standard ones, then those named in ``extra``.

    ``extra`` is the EXTRA_EXTENSIONS setting, module names separated by
    commas. It switches on the modules of single servers (``vow``,
    ``geuthur``) without editing ``config.py``.
    """
    names = list(standard)
    for raw in (extra or "").split(","):
        name = raw.strip().lower()
        if not name:
            continue
        # The name becomes part of an import path.
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError(f"{SETTING}: {raw.strip()!r} is not a module name.")
        if name not in names:
            names.append(name)
    return names
