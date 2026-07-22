# Changelog

## 0.1.3 – Coordinator: manuelle Fallbacks, unvollständige Einrichtung erkennen

- **Bugfix:** `_build_storage_capabilities` fällt auf manuelle kWh-/W-Werte zurück, wenn Entitätswerte fehlen oder leer sind (Fix für alte Einträge ab v0.1.2).
- **Bugfix:** `_parse_float_entity` parst auch reine Zahlenstrings direkt (manuelle kWh/W-Werte, keine HA-Entitäten).
- **Bugfix:** `_is_incomplete` erkennt auch fehlende manual-capacity/power Keys von Einträgen vor v0.1.3.
- **Bugfix:** Reconfigure-Flow verarbeitet Klick ohne Checkbox ohne Absturz.
- **TDD:** 3 neue Tests (manuelle Kapazität/Stromstärke → vollständig, Entität-Fallback auf manuell, Version ≠ 0.2).

## 0.1.4 – Test-Infrastruktur: vollständiger HA-Stub, Shadow-Safety-Tests, Integrationstests

- **Bugfix:** conftest.py bietet vollständigen Home-Assistant-Stub ohne native HA-Abhängigkeit — ermöglicht Tests in jeder isolierten Umgebung.
- **Bugfix:** config_flow integration tests aligned with conftest mock pattern — alle 5 Tests grün.
- **Bugfix:** async_unload_entry lifecycle vollständig getestet (test_integration_unload, test_coordinator_unload_cleanup).
- **TDD:** 30+ neue Tests durch verbesserten conftest-Stub (State, SensorEntity, FlowResult, dt_util, voluptuous).
- **Shadow-Safety:** Keine aktiven Steuerbefehle, keine Netz/HTTP, keine Switches/Selects — strikt lesend.

## 0.1.2 – UEM universal: e3dc_rscp optional, manual mapping, reconfigure, power modes

- **Bugfix:** UEM config flow no longer aborts with `e3dc_rscp_not_configured` when e3dc_rscp is not installed. Instead, the user is presented with a clear choice: cancel (set up adapter first) or continue with manual entity mapping.
- **Bugfix:** Reconfigure rescan with deleted e3dc_rscp entry correctly aborts with `e3dc_rscp_not_configured` instead of silently overwriting manual values.
- **Bugfix:** When e3dc discovery returns no entities, confirm step auto-redirects to manual_mapping (user is never blocked on an empty form).
- **New:** Battery capacity — choose entity (kWh) or manual kWh value.
- **New:** Max charge power — choose entity (W) or manual W value.
- **New:** Battery power — choose signed entity with explicit sign convention (`Laden positiv` / `Entladen positiv`) OR separate charge/discharge entities. No direction guessing.
- **New:** Grid power — choose signed entity with explicit sign convention (`Bezug positiv` / `Einspeisung positiv`) OR separate import/export entities.
- **New:** Coordinator detects incomplete setup (missing required entities) and reports `Shadow – Einrichtung unvollständig` instead of crashing or silently failing.
- **New:** Incomplete setup is clearly non-blocking: no control, no planning, unambiguous status.
- **TDD:** 14 new tests covering manual fixed values, power modes, signed conventions, Solar-only forecasts, shadow safety for incomplete setup, reconfigure no-overwrite, and version rule (0.1.x only).
- **UX:** All setup fields remain editable; setup can always be saved/resumed. Reconfigure never overwrites existing values.

## 0.1.1 – Shadow update

- Erweiterte Shadow-Planung mit generischen und Forecast.Solar-Prognosequellen.
- Zusätzliche lesende PV-Erzeugungs- und Gesamtlastsensoren.
- Robustere Behandlung fehlender, ungültiger oder unvollständiger Mess- und Forecast-Daten.
- Erweiterte lokale Home-Assistant-, Forecast- und Sicherheits-Tests.
- Strikte Shadow-Grenze wiederhergestellt: ausschließlich Sensoren; keine Switches, Selects, Services oder E3DC-Steuerbefehle.

## 0.1.0 – Initiale Shadow-Basis

- E3DC-RSCP-Erkennung und verpflichtender Shadow-Modus.
- Lesende Status-, Entscheidungs- und Soll-Ladelimit-Sensoren.
