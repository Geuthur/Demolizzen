"""Icons of the panel: a subset of Bootstrap Icons (MIT), drawn into the page.

The content security policy lets the panel load no icon font or sprite, so
``{% icon "name" %}`` writes the icon's SVG into the page itself. The files
live in ``static/icons`` next to their licence.
"""

# Standard Library
import re

# Django
from django import template
from django.utils.safestring import mark_safe

# Demolizzen
from demolizzen.web.base_settings import WEB_DIR

register = template.Library()

_SHAPES = re.compile(r"<svg[^>]*>(.*)</svg>", re.DOTALL)
# Size and colour come from the text around the icon (see .bi in panel.css).
_OPEN = (
    '<svg class="bi" viewBox="0 0 16 16" fill="currentColor" '
    'aria-hidden="true" focusable="false">'
)


def _load() -> dict[str, str]:
    icons = {}
    for path in sorted((WEB_DIR / "static" / "icons").glob("*.svg")):
        shapes = _SHAPES.search(path.read_text("utf-8")).group(1)
        icons[path.stem] = _OPEN + " ".join(shapes.split()) + "</svg>"
    return icons


# name -> markup. The files are ours, not user input.
ICONS: dict[str, str] = _load()

# The icon of each module, by its key in demolizzen.core.registry.
MODULE_ICONS = {
    "core": "cpu",
    "owner": "person-gear",
    "guild": "people",
    "panel": "sliders",
    "admin": "shield-lock",
    "general": "grid",
    "commands": "terminal",
    "levelsystem": "graph-up-arrow",
    "banksystem": "bank",
    "economy": "rocket-takeoff",
    "shop": "bag",
    "games": "dice-5",
    "eveonline": "globe2",
    "killmail": "crosshair",
    "ticket": "ticket-perforated",
}


def module_icon(key: str) -> str:
    """The name of a module's icon; a module without one of its own gets a
    neutral one."""
    return MODULE_ICONS.get(key, "hexagon-half")


@register.simple_tag
def icon(name: str) -> str:
    """Write the icon into the page."""
    try:
        return mark_safe(ICONS[name])  # nosec B308, B703 - our own static files
    except KeyError:
        raise template.TemplateSyntaxError(f"There is no icon {name!r}.") from None
