from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize(value: object) -> str:
    """Normalisiert Namen für Suche: Umlaute, ß, Groß-/Kleinschreibung, Leerraum."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("ß", "ss")
    return _WHITESPACE.sub(" ", text).strip()
