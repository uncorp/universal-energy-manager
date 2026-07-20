# UEM – Modell- und Datenfreigabe-Policy

Stand: 2026-07-18. Gilt für Planung, Implementierung, Review und spätere Releases.

## Grundsatz

UEM wird lokal-first entwickelt. Externe Modelle erhalten niemals Rohdaten aus Home Assistant oder E3DC.

## Datenklassen

### Ausschließlich lokal

- E3DC-IP, Zugangsdaten, Tokens und Backups
- Home-Assistant-Konfiguration, `.storage`, Diagnosedumps und Recorder-Rohdaten
- vollständige Entitätslisten, Haus-/PV-/Lastprofile und Zählerdaten
- reale Forecasts, Preisverläufe und Fahrzeugdaten aus dem Haushalt

### Bereinigt extern zulässig

- öffentlicher UEM-Quellcode
- synthetische/redigierte Testfixtures
- generische Fehlermeldungen ohne Anlagenbezug
- kleine, fachlich relevante Diffs

## Modellrollen

| Rolle | Standardmodell | Einsatz |
|---|---|---|
| Routine / schnelle Umsetzung | lokales Qwen | kleine Codeänderungen, Tests, Dokumentation, Strukturarbeiten |
| Tiefe lokale Gegenprüfung | lokales GLM-5.2 Colibri | Architekturvergleich, Diff-Review, Testfallentwurf, Analyse vorbereiteter lokaler Pakete; keine Tool-Calls |
| Externe Coding-Eskalation | Codex | nur bei bereinigtem öffentlichem Code, wenn Qwen nicht sinnvoll weiterkommt oder ein komplexer Tool-/Test-Task es rechtfertigt |
| Schwierige Nachtanalyse | GPT-5.6-Sol | derzeit keine allgemeine Freigabe (API-Limit erschöpft). Nur eine ausdrücklich pro Aufgabe erteilte Einmalfreigabe; stets kompaktes, bereinigtes Aufgabenpaket. |

Terra wird für UEM nicht verwendet.

## Token-Disziplin

- Qwen und GLM entscheiden frei über Routine- bzw. Gegenanalyseaufgaben.
- Externe Aufgaben sind klein zugeschnitten: Ziel, relevante Dateien/Diff, Tests, gewünschtes Ergebnis.
- Keine doppelte Vollkontextanalyse durch mehrere Modelle.
- Sol und Codex werden nicht für Routinearbeiten oder bloße Zusammenfassungen verwendet.

## Freigabegrenzen

- Keine externe Weitergabe privater Anlagen- oder Home-Assistant-Daten.
- Eine neue externe Abhängigkeit oder ein neues Cloud-Forecastkonto braucht eine separate Produktentscheidung.
- Das öffentliche GitHub-Repository enthält nur bereinigten Code, Dokumentation und synthetische Fixtures.
