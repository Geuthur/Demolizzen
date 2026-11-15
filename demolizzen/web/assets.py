"""The panel's own stylesheet and typeface."""

# Standard Library
import hashlib

# Demolizzen
from demolizzen.web.base_settings import WEB_DIR

STYLESHEET = (WEB_DIR / "static" / "panel.css").read_bytes()
FONT = (WEB_DIR / "static" / "exo2.woff2").read_bytes()


def version(content: bytes) -> str:
    """A short fingerprint of a file's content."""
    return hashlib.sha256(content).hexdigest()[:12]


# Pages link the stylesheet with this in its address, so a browser fetches it
# anew whenever it changed instead of styling new pages with an old copy.
STYLESHEET_VERSION = version(STYLESHEET)


def context(request) -> dict:  # pylint: disable=unused-argument
    """Template context: what the base template needs to link the assets."""
    return {"stylesheet_version": STYLESHEET_VERSION}
