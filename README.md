# nextbike-cli

Live-Verfügbarkeit von nextbike-Leihrädern im Terminal: Stadt per Name finden,
Stationen per Stichwort suchen, freie Räder und Stellplätze prüfen, Stationen in
der Nähe finden, ein Rad per Nummer nachschlagen und eine Station beobachten.
Lesend, ohne Login und ohne App.

## Schnellstart

```console
pipx install git+https://github.com/smlfg/nextbike-cli
nextbike staedte Mannheim
nextbike stationen Mannheim Lindenhof
nextbike station "Lindenhof - Jugendherberge" --stadt Mannheim
nextbike rad 431211 --stadt Mannheim
nextbike nah 49.4771,8.4637 --stadt Mannheim --radius 1200
nextbike watch "Lindenhof - Jugendherberge" --stadt Mannheim
```

Nach der Installation steht `nextbike` im PATH. Beim ersten Aufruf wird die
Städteliste geladen (24 h gecacht), Live-Daten einer Stadt 60 s.

## Befehle

| Befehl | Zweck |
|---|---|
| `nextbike staedte [SUCHE]` | Städte per Name finden (UID und Stationszahl) |
| `nextbike stationen STADT [SUCHBEGRIFF]` | Stationen einer Stadt per Stichwort suchen |
| `nextbike station NAME\|NUMMER [--stadt STADT]` | Details einer Station inklusive Radnummern |
| `nextbike nah LAT,LNG [--stadt STADT] [--radius M]` | Nächste Stationen mit Entfernung |
| `nextbike rad NUMMER [--stadt STADT]` | Station und Zustand eines Rads |
| `nextbike watch NAME [--stadt STADT] [--unter N]` | Verfügbarkeit beobachten und Änderungen melden |
| `nextbike config stadt STADT` | Standardstadt speichern |

### Beispiele

Stadt finden, auch teilweise:

```console
$ nextbike staedte Mannheim
Städte zu „Mannheim“ (2 Treffer):
Mannheim (UID 195, 112 Stationen)
Roche - Mannheim (UID 860, 41 Stationen)
```

Stationen per Stichwort:

```console
$ nextbike stationen Mannheim Lindenhof
Stationen in Mannheim zu „Lindenhof“ (6 Treffer):
25026 · Lindenhof - Jugendherberge · 3 ausleihbar, 3 Stellplätze frei
25028 · Lindenhof - Johanniskirche · 1 ausleihbar, 2 Stellplätze frei
25066 · Lindenhof - Meeräckerplatz · 15 ausleihbar, 0 Stellplätze frei
25067 · Lindenhof - Hanns-Glückstein-Park · 14 ausleihbar, 0 Stellplätze frei
25089 · Lindenhof / NTR · 0 ausleihbar, 0 Stellplätze frei
25096 · Lindenhofplatz / HBF Süd · 0 ausleihbar, 0 Stellplätze frei
```

Nur Stationen mit freien Rädern, mindestens drei:

```console
$ nextbike stationen Mannheim Lindenhof --min-raeder 3 --nur-frei
```

Stationsdetails inklusive Radnummern und Pedelec-Akkus:

```console
$ nextbike station "Lindenhof - Jugendherberge" --stadt Mannheim
Lindenhof - Jugendherberge (Station 25026)
Mannheim · 49.477082, 8.463662
Räder: 3 (3 ausleihbar) · Stellplätze frei: 3 von 6
Radtypen: 196 (3)
Radnummern: 430037, 430852, 430059
```

Rad per Nummer wiederfinden:

```console
$ nextbike rad 431211 --stadt Mannheim
Rad 431211 · Lindenhof - Meeräckerplatz (25066)
Mannheim · Typ 179 · Zustand ok
Akku: 100 % (ca. 60 km)
```

Stationen in der Nähe, nach Entfernung sortiert:

```console
$ nextbike nah 49.4771,8.4637 --stadt Mannheim --radius 1200
Stationen im Umkreis von 1200 m um 49.4771, 8.4637 (Mannheim):
3 m · Lindenhof - Jugendherberge (25026) · 3 ausleihbar, 3 Stellplätze frei
308 m · Lindenhofplatz / HBF Süd (25096) · 0 ausleihbar, 0 Stellplätze frei
431 m · Lindenhof - Johanniskirche (25028) · 1 ausleihbar, 2 Stellplätze frei
529 m · Lindenhof / NTR (25089) · 0 ausleihbar, 0 Stellplätze frei
694 m · Lindenhof - Hanns-Glückstein-Park (25067) · 14 ausleihbar, 0 Stellplätze frei
1021 m · Lindenhof - Meeräckerplatz (25066) · 15 ausleihbar, 0 Stellplätze frei
```

Station beobachten: Der erste Aufruf speichert den Stand, der nächste meldet
eine Veränderung. Mit `--unter N` warnt der Befehl unterhalb der Schwelle.

```console
$ nextbike watch "Lindenhof - Jugendherberge" --stadt Mannheim
Lindenhof - Jugendherberge (25026): 3 Räder verfügbar
Erster Aufruf – Stand gespeichert.
$ nextbike watch "Lindenhof - Jugendherberge" --stadt Mannheim
Lindenhof - Jugendherberge (25026): 3 Räder verfügbar
Unverändert seit letztem Aufruf.
```

## Konfiguration

Standardstadt einmal setzen, dann `--stadt` weglassen:

```console
$ nextbike config stadt Mannheim
Standardstadt: Mannheim (UID 195).
$ nextbike station "Lindenhof - Jugendherberge"
```

Pfade und Rechte:

| Datei | Pfad | Rechte |
|---|---|---|
| Config | `${XDG_CONFIG_HOME:-~/.config}/nextbike-cli/config.json` | 0600 |
| Cache | `${XDG_CACHE_HOME:-~/.cache}/nextbike-cli/` | Verzeichnis 0700 |
| Watch-Stand | `${XDG_STATE_HOME:-~/.local/state}/nextbike-cli/watch.json` | 0600 |

Die Städteliste wird 24 Stunden gecacht, Live-Daten einer Stadt 60 Sekunden. Die
Basis-URL lässt sich mit `NEXTBIKE_BASE_URL` überschreiben (Fake-Server, Tests).

## Ausgabe und Exit-Codes

Im Terminal erscheint lesbarer Text. Mit `--json` oder wenn stdout kein Terminal
ist, gibt das Tool genau ein JSON-Objekt aus. Fehler nennen den nächsten Schritt
und erzeugen keinen Traceback, auch nicht bei Strg+C oder EOF.

| Code | Bedeutung |
|---|---|
| 0 | Erfolg, auch Suche ohne Treffer und Watch mit Warnung |
| 1 | Fachlicher Fehler, z. B. Stadt, Station oder Rad nicht gefunden |
| 2 | Usage: falsche Argumente, mehrdeutige Treffer ohne TTY, fehlende Standardstadt |
| 3 | Netz- oder Quellenfehler (Verbindung, HTTP, JSON) |
| 4 | Voraussetzungen/Login nötig; in v1 reserviert |
| 130 | Abbruch per Strg+C |

`--version` und `--help` funktionieren überall und enden mit Exit 0.

## Hinweis

Dieses Werkzeug ist inoffiziell. Es nutzt die öffentlich erreichbare JSON-Karte
unter `https://maps2.nextbike.net/maps`, keine dokumentierte oder zugesicherte
API. Änderungen der Quelle können das Werkzeug brechen. Es werden ausschließlich
lesende GET-Anfragen gesendet; Ausleihe, Reservierung und Login sind nicht Teil
von v1. Es werden keine Konten, Secrets oder Personendaten verarbeitet oder
gespeichert.

## Entwicklung

Die UX-Spec steht in [docs/UX.md](docs/UX.md), der Schnittstellenvertrag in
[INTERFACE.md](INTERFACE.md), die Anforderungen in
[ANFORDERUNGEN.md](ANFORDERUNGEN.md).

Vor dem Bau prüfen:

```bash
python3 tests/harness/ux_check.py . --spec-only
```

Nach dem Bau müssen UX-Gate und Sitzungen grün sein:

```bash
python3 tests/harness/ux_check.py .
python3 tests/harness/ux_session.py .
```

Akzeptanztests gegen den Fake-Server:

```bash
python3 -m pytest -q tests/acceptance
```

## Lizenz

MIT, Copyright smlfg. Siehe [LICENSE](LICENSE).
