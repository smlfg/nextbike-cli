# Pflicht-QA nextbike-cli

- Datum: 2026-11-17
- Version: 0.1.0
- Commit: 5aec285 (origin/main, Arbeitsbaum sauber)
- Nachprüfung: 2026-11-17 nach Fix 5ec9800 (`fix: Tippfehler-Fallback fuer Stationsnamen mit Praefix`); Live-Befehl erneut ausgeführt, `pytest` 55 passed, `ux_check.py`/`ux_session.py` je Exit 0.
- Prüfer: unabhängige QA-Iteration (find -> file, kein Code-Fix)
- Installation: `pipx install git+https://github.com/smlfg/nextbike-cli` in `./scratch/pipx` (Protokoll `scratch/qa/pipx-install.log`), jeder Aufruf über `PATH=$PWD/scratch/pipx/bin:$PATH`.
- Live-Zugriffe: ausschließlich lesende GETs gegen `https://maps2.nextbike.net/maps`. Kein Login, keine schreibende Aktion; UX09/Login ist laut `docs/UX.md` nicht Teil von v1 (SKIP).
- Pseudo-Terminal: `script -qc "<befehl>" scratch/qa/<n>.log`; JSON-Prüfungen zusätzlich über Pipe und `--json`.

## Befunde

| Prüfung | Befehl | Erwartet | Ergebnis | Beleg (gekürzt) |
|---|---|---|---|---|
| Frische pipx-Installation | `PIPX`-Protokoll + `nextbike --version` | installiert, `nextbike` im PATH | OK | `installed package nextbike-cli 0.1.0`; `nextbike 0.1.0` |
| Installierter Stand = HEAD | `cmp src/nextbike/*.py scratch/pipx/.../nextbike/*.py` | identischer Code | OK | 7/7 Dateien `same` |
| Version | `nextbike --version` | Exit 0, Version | OK | `nextbike 0.1.0`, Exit 0 |
| Hilfe | `nextbike --help` und `--help` je Subcommand | Exit 0, verständlich | OK | alle 8 Aufrufe Exit 0 |
| Schnellstart Stadt | `nextbike staedte Mannheim` | Treffer mit UID/Stationszahl | OK | 2 Treffer: Mannheim (UID 195), Roche - Mannheim (UID 860) |
| Schnellstart Stationen | `nextbike stationen Mannheim Lindenhof` | Treffer mit Nummer/Name/Rädern | OK | 6 Treffer, z. B. `25026 · Lindenhof - Jugendherberge · 5 ausleihbar, 1 Stellplätze frei` |
| Schnellstart Stationsdetail | `nextbike station "Lindenhof - Jugendherberge" --stadt Mannheim` | Details inkl. Radnummern | OK | Station 25026, `Radnummern: 42814, 430037, 430852, 431707, 432300` |
| Schnellstart Rad | `nextbike rad 431211 --stadt Mannheim` | Station/Typ/Zustand/Akku | OK | `Rad 431211 · Lindenhof - Meeräckerplatz (25066)`, `Akku: 99 % (ca. 59 km)` |
| Schnellstart Nähe | `nextbike nah 49.4771,8.4637 --stadt Mannheim --radius 1200` | nach Entfernung sortiert | OK | 21 Treffer, 3 m … 1195 m, aufsteigend |
| Schnellstart Watch | `nextbike watch ...` zweimal | erster Aufruf speichert, zweiter unverändert | OK | `Erster Aufruf – Stand gespeichert.` / `Unverändert seit letztem Aufruf.` |
| Standardstadt | `nextbike config stadt Mannheim`; danach `station` ohne `--stadt` | gespeichert und genutzt | OK | `Standardstadt: Mannheim (UID 195).`; Detail kommt ohne `--stadt` |
| Dateirechte | `stat -c '%a' config.json watch.json` | 0600, Verzeichnisse 0700 | OK | 600/600, Verzeichnisse 700 |
| Fake-Server / base_url_env | alle README-Befehle gegen `tests/harness/fake_server.py` mit `ux-routes` | Request am Fake-Server, erwartete Ausgabe | OK | 2 Requests (`list_cities=1`, `city=195`); TTY-Ausgabe = README-Beispiele |
| Cache | 7 Fake-Befehle in Folge | Städteliste/Stadt nur einmal geladen | OK | 7 Läufe, genau 2 GETs |
| Ausgabe TTY vs. Pipe | `script`-TTY bzw. Pipe/`--json` | Text im TTY, sonst genau ein JSON | OK | TTY lesbarer Text; Pipe `{"staedte": ...}` |
| `--json`-Position | `nextbike --json staedte Mannheim` und `nextbike staedte Mannheim --json` | beide valide JSON | OK | beide Exit 0, parsebar |
| Filter `--nur-frei` | `nextbike --json stationen Mannheim --nur-frei` | jeder Treffer `ausleihbar >= 1` | OK | 86/86 Treffer, 0 Verstöße |
| Filter `--min-raeder 3` | `nextbike --json stationen Mannheim --min-raeder 3` | jeder Treffer `ausleihbar >= 3` | OK | 60/60 Treffer, 0 Verstöße |
| Filter kombiniert | `... Lindenhof --min-raeder 3 --nur-frei` | alle Filter je Treffer | OK | 4/4 Treffer, 0 Verstöße |
| Suchbegriff | `nextbike --json stationen Mannheim Lindenhof` | jeder Treffer enthält Suchbegriff | OK | 6/6 Treffer |
| Radius/Sortierung | `nextbike --json nah ... --radius 1200` | alle `<= 1200`, aufsteigend | OK | 21/21, Maximum 1195 m |
| Leeres Ergebnis Nähe | `nextbike --json nah 0,0 --stadt Mannheim --radius 1` | Hinweis, Exit 0 | OK | `"stationen": []`, Exit 0 |
| Leeres Ergebnis Suche | `nextbike --json stationen Mannheim XyzNope` | Hinweis, Exit 0 | OK | `"stationen": []`, Exit 0 |
| Stadt mit Tippfehler | `nextbike --json staedte Mannhein` | Mannheim gefunden | OK | Treffer Mannheim (UID 195) |
| Umlaute | `staedte Munchen`, `station Meerackerplatz` | München bzw. Meeräckerplatz | OK | beide Exit 0, richtige Namen |
| Station mit Tippfehler | `nextbike --json station Jugendherbrge --stadt Mannheim` | Tippfehler-Fallback laut `INTERFACE.md` | OK (nach Fix 5ec9800) | Exit 0, Station 25026 `Lindenhof - Jugendherberge`; ebenso `Meerackerplaz` → 25066, `Lindenhopf` → Exit 2 mit Lindenhof-Kandidaten |
| Mehrdeutige Stadt im TTY | `printf '1\n' \| script -qc "nextbike stationen Mann"` | nummerierte Auswahl | OK | `1. Mannheim … 3. Roche - Mannheim`, Auswahl 1 liefert Mannheim |
| Mehrdeutig ohne TTY | `nextbike --json stationen Mann` | Exit 2 mit Kandidatenliste | OK | `code: MEHRDEUTIG`, `kandidaten: [...]`, Exit 2 |
| Station nicht gefunden | `nextbike --json station "Gibt Es Nicht" --stadt Mannheim` | Exit 1, nächster Schritt | OK | `STATION_NICHT_GEFUNDEN`, `naechster_schritt: Nutze nextbike stationen …` |
| Rad nicht gefunden | `nextbike --json rad 1 --stadt Mannheim` | Exit 1, nächster Schritt | OK | `RAD_NICHT_GEFUNDEN`, Exit 1 |
| Netz unerreichbar | `NEXTBIKE_BASE_URL=http://127.0.0.1:9/maps nextbike staedte Mannheim` | Exit 3, kein Traceback | OK | `ConnectError`, `Prüfe die Verbindung …`, Exit 3 |
| Basis-URL ungültig | `NEXTBIKE_BASE_URL=keine-url nextbike staedte Mannheim` | Exit 3, kein Traceback | OK | `keine gültige http(s)-Basis-URL`, Exit 3 |
| Ungültige Argumente | Koordinaten `999,0`, `--min-raeder -1`, unbekannter Befehl | Exit 2 als JSON | OK | jeweils `code: USAGE`, Exit 2 |
| EOF in Auswahl | leere Eingabe an `stationen Mann` | Exit 2, kein Traceback | OK | `Keine Auswahl getroffen …`, Exit 2 |
| Strg+C | SIGINT während laufendem GET | Exit 130, kein Traceback | OK | `Abgebrochen.`, Exit 130 |
| Kaputter Watch-Stand | ungültiges `watch.json`, dann `watch` | Hinweis, erster Aufruf | OK | `Hinweis: Watch-Stand ist unlesbar …`, Exit 0 |
| Fehlende Standardstadt | `station ...` in frischem XDG ohne Config | Exit 2, beide Wege genannt | OK | `Nutze nextbike config stadt STADT oder --stadt STADT.` |
| Watch-Schwelle | `nextbike watch ... --unter 10` | Warnung, Exit 0 | OK | `Warnung: 5 ausleihbar, unter Schwelle 10.` |
| Tests | `scratch/venv/bin/pytest -q` | grün | OK | `55 passed` (nach Fix 5ec9800) |
| Login-Sitzung | – | read-only, kein Login in v1 | SKIP | Kein `login`-Befehl, keine `credential_env`; laut `docs/UX.md` UX09 entfällt |

## Zählung

- **39 OK**, **0 FAIL**, **1 SKIP** (gesamt 40 Zeilen; 39 geprüft, 1 SKIP) nach Nachprüfung und Fix 5ec9800.
- Live-Zahlen weichen von den README-Beispielen ab (z. B. 107 statt 112 Stationen, 21 statt 6 Treffer im Radius, Akku 99 % statt 100 %). Das sind dynamische Live-Daten, kein Fehler.

## Offene FAILs

Keine. Der einzige FAIL (Station-Tippfehler-Fallback bei kurzen Tippvarianten) ist mit Commit 5ec9800 behoben und live nachgeprüft: `nextbike --json station Jugendherbrge --stadt Mannheim` liefert Exit 0 und `Lindenhof - Jugendherberge (25026)`.
