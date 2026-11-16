# Interface: nextbike-cli

Vertrag für Implementierung und Agenten. Der Konsolenbefehl heißt `nextbike`,
das Python-Paket `nextbike` (startbar mit `python -m nextbike`).

## Aufruf

```text
nextbike [--json] [--version] [--help] BEFEHL [ARGUMENTE] [OPTIONEN]
```

`--json` darf vor dem Befehl oder direkt beim Befehl stehen. `--version` und
`--help` funktionieren auch ohne Befehl und enden mit Exit 0.

Ohne `--json` gilt: Ist stdout ein Terminal, wird lesbarer Text ausgegeben; ist
stdout kein Terminal (Pipe, Datei, Agent), wird genau ein JSON-Objekt
ausgegeben. Prompts und Warnungen gehen immer auf stderr.

## Befehle

### `nextbike staedte [SUCHE]`

Sucht Städte in der 24 h gecachten Städteliste.

- Ohne `SUCHE`: alle Städte, alphabetisch sortiert.
- Mit `SUCHE`: normalisierter Teilstring-Vergleich (Groß-/Kleinschreibung und
  Umlaute egal), danach Tippfehler-Fallback. Sortierung: exakter Name, Präfix,
  Teilstring, dann alphabetisch.
- Textausgabe:

  ```text
  Städte zu „Mannheim“ (2 Treffer):
  Mannheim (UID 195, 112 Stationen)
  Roche - Mannheim (UID 860, 41 Stationen)
  ```

- Keine Treffer: Hinweis auf stdout, Exit 0.

### `nextbike stationen STADT [SUCHBEGRIFF] [--min-raeder N] [--nur-frei]`

Sucht Stationen innerhalb einer Stadt.

- `STADT` ist positional und wird wie bei `staedte` aufgelöst. Ein exakter
  Stadtname gewinnt gegen Teilstring-Treffer; mehrere gleichwertige Treffer
  führen im TTY zu einer nummerierten Auswahl, sonst zu einer Liste mit Exit 2.
- `SUCHBEGRIFF` ist optional; ohne ihn werden alle Stationen der Stadt gelistet.
  Vergleich normalisiert als Teilstring auf `name`.
- `--min-raeder N`: nur Stationen mit mindestens `N` ausleihbaren Rädern
  (`bikes_available_to_rent`), `N >= 0`.
- `--nur-frei`: nur Stationen mit mindestens einem ausleihbaren Rad.
- Freistehende Räder (`bike: true`) zählen nicht als Station und werden hier
  ausgeblendet.
- Textausgabe:

  ```text
  Stationen in Mannheim zu „Lindenhof“ (6 Treffer):
  25026 · Lindenhof - Jugendherberge · 3 ausleihbar, 3 Stellplätze frei
  ...
  ```

- Reihenfolge: Reihenfolge der Quelle. Keine Treffer: Hinweis, Exit 0.

### `nextbike station NAME|NUMMER [--stadt STADT]`

Zeigt Details einer Station.

- `NAME|NUMMER`: rein numerisch wird als Stationsnummer interpretiert, sonst als
  Name (normalisiert; exakter Name vor Teilstring). Mehrdeutige Namen: TTY-Auswahl,
  sonst Liste plus Exit 2.
- `--stadt STADT`: Stadt des Aufrufs. Fehlt sie, gilt die Standardstadt aus
  `nextbike config stadt`. Ist keine gesetzt, endet der Befehl mit Exit 2 und
  nennt beide Möglichkeiten.
- Textausgabe (Beispiel):

  ```text
  Lindenhof - Jugendherberge (Station 25026)
  Mannheim · 49.477082, 8.463662
  Räder: 3 (3 ausleihbar) · Stellplätze frei: 3 von 6
  Radtypen: 196 (3)
  Radnummern: 430037, 430852, 430059
  ```

- Zusätzliche Zeilen nur bei Bedarf: `Wartung: ja` bei `maintenance: true`,
  `Hinweis: Station ist deaktiviert` bei `active_place: 0`. Ohne Räder:
  `Radnummern: –`.
- Koordinaten mit bis zu sechs Nachkommastellen, ohne überflüssige Nullen.
- Radtypen numerisch sortiert (`71 (1), 150 (1), 179 (3), 196 (10)`).
- Nicht gefunden: Exit 1 mit nächstem Schritt.

### `nextbike nah LAT,LNG [--stadt STADT] [--radius M]`

Findet Stationen im Umkreis.

- `LAT,LNG` positional, Komma-getrennt, optional mit Leerzeichen. Zahlen werden
  validiert (`-90..90`, `-180..180`); sonst Exit 2.
- `--stadt STADT`: optional. Ohne Angabe gilt die Standardstadt. Ist keine
  gesetzt, wird aus den Stadtmittelpunkten der gecachten Städteliste die
  nächstgelegene Stadt gewählt.
- `--radius M`: Radius in Metern, ganzzahlig `>= 1`, Standard `1000`.
- Entfernung per Haversine, gerundet auf ganze Meter. Sortierung: Entfernung,
  dann Stationsname.
- Nur echte Stationen (`bike: false`) werden gelistet.
- Textausgabe:

  ```text
  Stationen im Umkreis von 1200 m um 49.4771, 8.4637 (Mannheim):
  3 m · Lindenhof - Jugendherberge (25026) · 3 ausleihbar, 3 Stellplätze frei
  ...
  ```

- Keine Station im Radius: Hinweis mit Vorschlag, `--radius` zu erhöhen, Exit 0.

### `nextbike rad NUMMER [--stadt STADT]`

Findet ein Rad per Nummer.

- `NUMMER` ist die Radnummer aus `bike_list[].number` bzw. `bike_numbers[]`.
- `--stadt STADT` wie bei `station`. Ohne `--stadt` gilt die Standardstadt; ohne
  Standardstadt Exit 2 mit nächstem Schritt.
- Sucht auch in freistehenden Rädern (`bike: true`).
- Textausgabe (Beispiel):

  ```text
  Rad 431211 · Lindenhof - Meeräckerplatz (25066)
  Mannheim · Typ 179 · Zustand ok
  Akku: 100 % (ca. 60 km)
  ```

- Akkuzeile nur bei `pedelec_battery`/`battery_pack`; Prozent und
  `estimated_range_km` werden übernommen. Bei freistehendem Rad entfällt die
  Stationsnummer (Ausgabe nennt den Platznamen).
- Nicht gefunden: Exit 1 mit Hinweis auf `--stadt` und `nextbike stationen`.

### `nextbike watch NAME [--stadt STADT] [--unter N]`

Vergleicht die Verfügbarkeit einer Station mit dem letzten Aufruf.

- Auflösung von `NAME` und `--stadt` wie bei `station`.
- `--unter N`: Warnschwelle für ausleihbare Räder, ganzzahlig `>= 0`.
- Beim ersten Aufruf für diese Station: Stand speichern und
  `Erster Aufruf – Stand gespeichert.` ausgeben.
- Danach: `Unverändert seit letztem Aufruf.` oder
  `Verändert seit letztem Aufruf: 3 → 2 ausleihbar.`
- Unterschreitet die aktuelle Zahl die Schwelle:
  `Warnung: 2 ausleihbar, unter Schwelle 3.` Watch endet auch mit Warnung mit
  Exit 0 (Beobachtung, keine schreibende Aktion).
- Zustandsdatei: `${XDG_STATE_HOME:-~/.local/state}/nextbike-cli/watch.json`,
  Rechte 0600, Verzeichnis 0700. Unlesbarer Zustand wird wie ein erster Aufruf
  behandelt (Hinweis auf stderr), nie als Traceback.

### `nextbike config stadt [STADT]`

- Mit `STADT`: löst die Stadt auf, speichert UID und Namen und gibt
  `Standardstadt: Mannheim (UID 195).` aus.
- Ohne `STADT`: zeigt die gespeicherte Standardstadt oder einen Hinweis, wie sie
  gesetzt wird.
- Config-Datei: `${XDG_CONFIG_HOME:-~/.config}/nextbike-cli/config.json`,
  Rechte 0600, Verzeichnis 0700.

## Auflösung von Städten und Namen

- Normalisierung: Unicode-NFKD, kombinierende Zeichen entfernen, `ß` → `ss`,
  Kleinschreibung, Leerraum vereinheitlichen. Umlaute werden damit auf ihre
  Grundbuchstaben reduziert (`München` = `Munchen`).
- Stadt: exakter Treffer gewinnt; sonst eindeutiger Teilstring; sonst
  Tippfehler-Fallback (`difflib`, Cutoff 0.75). Mehrere gleichwertige Treffer:
  TTY-Auswahl, sonst Liste plus Exit 2.
- Station: exakter Name gewinnt; sonst eindeutiger Teilstring; sonst
  Tippfehler-Fallback. Numerische Eingabe wird exakt gegen `number` geprüft.

## Ausgabeformate

Menschenausgabe nutzt `·` als Trenner und deutsche Anführungszeichen `„…“`.
Keine ANSI-Farben, wenn `NO_COLOR` gesetzt ist oder stdout kein TTY ist.

### JSON

Bei `--json` oder nicht-TTY steht genau ein JSON-Objekt auf stdout. Fehler
werden ebenfalls als genau ein Objekt ausgegeben:

```json
{"fehler": {"code": "STADT_NICHT_GEFUNDEN", "nachricht": "Stadt „Mannheimx“ nicht gefunden.", "naechster_schritt": "nextbike staedte Mannheim"}}
```

Erfolgsobjekte (Auszug):

```json
{"staedte": [{"uid": 195, "name": "Mannheim", "num_places": 112}], "suche": "Mannheim"}
{"stadt": {"uid": 195, "name": "Mannheim"}, "suche": "Lindenhof", "stationen": [{"nummer": 25026, "name": "Lindenhof - Jugendherberge", "ausleihbar": 3, "freie_stellplaetze": 3}]}
{"station": {"nummer": 25026, "name": "Lindenhof - Jugendherberge", "stadt": {"uid": 195, "name": "Mannheim"}, "lat": 49.477082, "lng": 8.463662, "raeder": 3, "ausleihbar": 3, "stellplaetze": 6, "freie_stellplaetze": 3, "wartung": false, "radtypen": {"196": 3}, "radnummern": [430037, 430852, 430059]}}
{"mittelpunkt": {"lat": 49.4771, "lng": 8.4637}, "radius_m": 1200, "stadt": {"uid": 195, "name": "Mannheim"}, "stationen": [{"entfernung_m": 3, "nummer": 25026, "name": "Lindenhof - Jugendherberge", "ausleihbar": 3, "freie_stellplaetze": 3}]}
{"radnummer": 431211, "stadt": {"uid": 195, "name": "Mannheim"}, "station": {"nummer": 25066, "name": "Lindenhof - Meeräckerplatz"}, "typ": "179", "zustand": "ok", "akku": {"prozent": 100, "reichweite_km": 60}}
{"station": {"nummer": 25026, "name": "Lindenhof - Jugendherberge", "stadt": {"uid": 195, "name": "Mannheim"}}, "verfuegbar": 3, "vorher": 3, "veraendert": false, "erster_aufruf": false, "schwelle": null, "warnung": false}
{"standardstadt": {"uid": 195, "name": "Mannheim"}}
```

Feldnamen und -typen sind stabil. Zusätzliche Felder dürfen ergänzt, aber nicht
umbenannt werden.

## Exit-Codes

| Code | Bedeutung |
|---|---|
| 0 | Erfolg, auch Suche ohne Treffer und Watch mit Warnung |
| 1 | Fachlicher Fehler: Stadt/Station/Rad nicht gefunden, keine verwertbaren Daten |
| 2 | Usage: unbekannter Befehl/Flag, fehlende/ungültige Argumente, mehrdeutig ohne TTY, fehlende Standardstadt, abgebrochene Auswahl/EOF |
| 3 | Netz- oder Quellenfehler: Verbindung, Timeout, HTTP ≠ 200, kaputtes JSON, unerwartetes Schema |
| 4 | Voraussetzungen/Login nötig; in v1 reserviert und nie zurückgegeben |
| 130 | Abbruch per Strg+C, ohne Traceback |

## Umgebungsvariablen

| Variable | Wirkung |
|---|---|
| `NEXTBIKE_BASE_URL` | überschreibt `https://maps2.nextbike.net/maps` (Fake-Server/Tests) |
| `XDG_CONFIG_HOME` | Basis für `nextbike-cli/config.json` |
| `XDG_CACHE_HOME` | Basis für Städteliste (24 h) und Live-Daten (60 s) |
| `XDG_STATE_HOME` | Basis für `watch.json` |
| `XDG_DATA_HOME` | reserviert, wird nicht benötigt |
| `NO_COLOR` | keine Farben (Farben sind in v1 ohnehin optional) |

Es gibt keine Zugangsdaten und keine `*_LOGIN_*`-Variablen. Die nextbike-Karte
ist öffentlich; Ausleihe läuft ausschließlich über die App.

## Dateien und Cache

- Config: `${XDG_CONFIG_HOME:-~/.config}/nextbike-cli/config.json` (0600)
- Cache: `${XDG_CACHE_HOME:-~/.cache}/nextbike-cli/` — Städteliste 24 h,
  Stadt-Daten 60 s; Cache-Schlüssel enthält die Basis-URL, damit Fake- und
  Live-Daten sich nicht vermischen.
- State: `${XDG_STATE_HOME:-~/.local/state}/nextbike-cli/watch.json` (0600)
- Alle Dateien werden atomar geschrieben (Tempdatei im Zielverzeichnis,
  `os.replace`). Verzeichnisse 0700, persönliche Dateien 0600.
- Unlesbare oder kaputte Cache-/State-Dateien werden ignoriert und neu
  aufgebaut; das erzeugt keinen Traceback.

## Fehlerverhalten

- Erst HTTP-Status prüfen, dann JSON parsen, dann Schema prüfen.
- Jede Fehlerklasse hat genau einen Exit-Code (siehe oben).
- Fehlermeldungen nennen den nächsten Schritt, z. B.
  `Stadt „Mannheimx“ nicht gefunden. Nutze nextbike staedte Mannheim.`
- `--json` und nicht-TTY: auch Usage-Fehler liefern genau ein JSON-Objekt.
- Keine Tracebacks bei fehlender Verbindung, kaputtem JSON, EOF, Strg+C oder
  fehlenden Rechten.
