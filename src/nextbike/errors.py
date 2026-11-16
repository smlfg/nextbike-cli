from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CliError(Exception):
    """Fehler mit stabiler Klasse, Exit-Code und nächstem Schritt."""

    slug: str
    message: str
    next_step: str | None = None
    exit_code: int = 1
    kandidaten: list[Any] = field(default_factory=list)

    def __str__(self) -> str:
        if self.next_step:
            return f"{self.message} {self.next_step}"
        return self.message


def usage(message: str, next_step: str = "Nutze nextbike --help.") -> CliError:
    return CliError("USAGE", message, next_step, 2)


def not_found(slug: str, message: str, next_step: str) -> CliError:
    return CliError(slug, message, next_step, 1)


def source_error(message: str, next_step: str | None = None) -> CliError:
    return CliError(
        "QUELLE_FEHLER",
        message,
        next_step or "Prüfe die Verbindung und versuche es später erneut.",
        3,
    )
