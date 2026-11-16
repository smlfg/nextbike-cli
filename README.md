# nextbike-cli

Live-Verfügbarkeit von nextbike-Leihrädern im Terminal: Stadt per Name finden, Stationen per Stichwort suchen, freie Räder und Stellplätze prüfen, Stationen in der Nähe finden, ein Rad per Nummer nachschlagen und eine Station beobachten. Lesend, ohne Login und ohne App.

## Schnellstart

```console
pipx install git+https://github.com/smlfg/nextbike-cli
nextbike stationen Mannheim Lindenhof
nextbike station "Lindenhof - Jugendherberge" --stadt Mannheim
```

## Befehle

| Befehl | Zweck |
|---|---|
| `nextbike staedte [SUCHE]` | Städte per Name finden (UID und Stationszahl) |
| `nextbike stationen STADT [SUCHBEGRIFF]` | Stationen einer Stadt per Stichwort suchen |
| `nextbike station NAME\|NUMMER [--stadt STADT]` | Details einer Station inklusive Radnummern |
| `nextbike nah LAT,LNG [--stadt STADT] [--radius M]` | Nächste Stationen mit Entfernung |
| `nextbike rad NUMMER [--stadt STADT]` | Station und Zustand eines Rads |
| `nextbike watch NAME [--unter N]` | Verfügbarkeit beobachten und Änderungen melden |
| `nextbike config stadt STADT` | Standardstadt speichern |

Ohne TTY oder mit `--json` gibt das Tool JSON aus. Fehler nennen den nächsten Schritt und enden ohne Traceback. `--version` und `--help` funktionieren überall.

## Daten und Zwischenspeicher

Die öffentliche nextbike-Karte liegt unter `https://maps2.nextbike.net/maps`. Die Städteliste wird 24 Stunden gecacht, Live-Daten 60 Sekunden. Standardstadt, Cache und Watch-Stand liegen unter `~/.config`, `~/.cache` bzw. `~/.local/state` in `nextbike-cli`-Verzeichnissen; Dateien mit persönlichen Einstellungen haben Rechte 0600.

Für Tests und Fake-Server lässt sich die Basis-URL mit `NEXTBIKE_BASE_URL` überschreiben.

## Entwicklung

Die UX-Spec steht in [docs/UX.md](docs/UX.md). Vor dem Bau prüfen:

```bash
python3 tests/harness/ux_check.py . --spec-only
```

Nach dem Bau müssen UX-Gate und Sitzungen grün sein:

```bash
python3 tests/harness/ux_check.py .
python3 tests/harness/ux_session.py .
```

Lizenz: MIT, Copyright smlfg.
