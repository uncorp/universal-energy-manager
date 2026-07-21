# Changelog

## 0.1.2 – UEM universal: e3dc_rscp optional, manual mapping, reconfigure fix

- **Bugfix:** UEM config flow no longer aborts with `e3dc_rscp_not_configured` when e3dc_rscp is not installed. Instead, the user is presented with a clear choice: cancel (set up adapter first) or continue with manual entity mapping.
- **Bugfix:** Reconfigure rescan with deleted e3dc_rscp entry correctly aborts with `e3dc_rscp_not_configured` instead of silently overwriting manual values.
- **TDD:** New test suite verifies no-abort path in fresh HAOS without e3dc_rscp (4 new tests).

## 0.1.1 – Shadow update

- Erweiterte Shadow-Planung mit generischen und Forecast.Solar-Prognosequellen.
- Zusätzliche lesende PV-Erzeugungs- und Gesamtlastsensoren.
- Robustere Behandlung fehlender, ungültiger oder unvollständiger Mess- und Forecast-Daten.
- Erweiterte lokale Home-Assistant-, Forecast- und Sicherheits-Tests.
- Strikte Shadow-Grenze wiederhergestellt: ausschließlich Sensoren; keine Switches, Selects, Services oder E3DC-Steuerbefehle.

## 0.1.0 – Initiale Shadow-Basis

- E3DC-RSCP-Erkennung und verpflichtender Shadow-Modus.
- Lesende Status-, Entscheidungs- und Soll-Ladelimit-Sensoren.
