# UX-Gate-Bericht

- Datum: 16.11.2026
- Repo: `/home/box/cli-daily/nextbike-cli`
- Tool: `nextbike`
- Harness unverändert.

## Ergebnis

| Prüfung | Exit-Code |
|---|---|
| `python3 tests/harness/ux_check.py . --report scratch/ux_check.md` | 0 |
| `python3 tests/harness/ux_session.py . --report scratch/ux_session.md` | 0 |

## ux_check.py

- Repo: `/home/box/cli-daily/nextbike-cli`
- Tool: `nextbike`
- Modus: voll
- Ergebnis: PASS

| ID | Ergebnis | Befund |
|---|---|---|
| UX00 | PASS | 2 Request(s) am Fake-Server, keine Fremdverbindung |
| UX01 | PASS | docs/UX.md: 6 Sitzungen, 0 formsteps |
| UX02 | PASS | keine Credential-Env-Variablen gefunden |
| UX03 | PASS | --help, --version und 7 Unterkommandos mit Exit 0 |
| UX04 | PASS | 7 Unterkommandos ohne Pflicht-Option statt positional |
| UX05 | PASS | 6 Sitzungen ohne JSON/Traceback im TTY |
| UX06 | PASS | Schnellstart: 6 Tool-Befehle, Installation passt |
| UX07 | PASS | keine ux-formsteps, keine schreibende Aktion |
| UX08 | PASS | keine ux-formsteps, keine schreibende Aktion |
| UX09 | SKIP | keine schreibende Sitzung |

## ux_session.py

- Tool: `nextbike`
- Repo: `/home/box/cli-daily/nextbike-cli`
- Ergebnis: PASS

| Sitzung | Lauf | Ergebnis | Befund |
|---|---|---|---|
| Installation und Städte finden | 1 | PASS | OK |
| Stationen per Stichwort suchen | 1 | PASS | OK |
| Station im Detail anzeigen | 1 | PASS | OK |
| Rad per Nummer finden | 1 | PASS | OK |
| Stationen in der Nähe | 1 | PASS | OK |
| Station beobachten | 1 | PASS | OK |

## Tests

- `scratch/venv/bin/pytest -q` → 52 passed.
