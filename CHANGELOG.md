# Changelog

## 0.1.10 – Grid-Vorzeichen- und Shadow-Testbeta

- **Fix:** E3DC-RSCP `grid-netchange` folgt nun durchgängig der UEM-Konvention: Netzbezug positiv, Einspeisung negativ. Abweichende Quellen können ihr Vorzeichen explizit umkehren.
- **UX:** Die Netz-Vorzeichenoption ist ein klarer Boolean-Schalter; Reconfigure und E3DC-Rescan bewahren die Auswahl.
- **Shadow-Safety:** UEM bleibt sensor-only: keine aktiven Steuerbefehle, `active_control=false` und `commands_sent=false`.
- **Test:** Vollständige Regressionen für Vorzeichen, Schema, Rescan und unvollständige Shadow-Konfigurationen.

## 0.1.9 – Config-Flow-Korrekturen als Test-Beta

- **Fix:** Manuelle Zuordnung verwendet verständlichere Netz-Vorzeichenbeschreibungen und standardmäßig „Netzbezug positiv“.
- **Fix:** Die Konfigurationsdialoge enthalten die für Home Assistant 2024.3.x erforderlichen Platzhalter in den Feldbeschreibungen.
- **Fix:** Signierte Werte für Hauslast, Netzeinspeisung und Batterieladung werden im manuellen Mapping akzeptiert.
- **Test:** Erweiterte Regressionstests für leere und unvollständige Shadow-Konfigurationen, Reconfigure, Feldbeschreibungen und Vorzeichenkonventionen.

## 0.1.8 – Optionale, gruppierte manuelle Entitätszuordnung

- **UX:** Manuelle Zuordnung ist weiterhin eine Seite, aber Messwerte sind verständlich gruppiert: allgemeine Werte, alle Batterie-Felder zusammen und alle Netz-Felder zusammen.
- **UX:** Batterie und Netz verwenden standardmäßig jeweils eine Leistungsentität. Die Auswahl erklärt in Klartext, ob positive Werte Laden/Entladen bzw. Einspeisung/Netzbezug bedeuten. Zwei getrennte Entitäten bleiben optional verfügbar.
- **UX:** Keine Entität ist beim Speichern Pflicht. „Später einrichten“ legt einen sicheren, bewusst unvollständigen Shadow-Eintrag an; UEM berechnet oder steuert ohne genügend Daten nichts.
- **Fix:** Der bisher fehlende Speicherschritt für „Konfigurieren → Manuelle Zuordnung bearbeiten“ aktualisiert und lädt den Eintrag jetzt korrekt neu.
- **Test:** Regressionstests decken leeres Speichern, spätere Einrichtung, optionale Kapazitäts-/Leistungsfelder, Feldgruppierung und das spätere Speichern ab.

## 0.1.7 – Shadow-MVP-Release: 100 % Statement Coverage, 328 Tests, Ruff clean

- **Bugfix:** `_parse_float_entity` fängt `unhashable type: 'State.state'` ab (Coordinator crashed bei nicht-hashbarem state.state).
- **Bugfix:** Unreachable-else-Branch in `entity_data`-Merge entfernt (2 Branch-Parts verbleiben als dokumentierte, provably-unreachable Edge-Cases).
- **Bugfix:** `home-assistant-bluetooth==1.13.0` Resolver-Konflikt behoben (explizite Abhängigkeit).
- **Test:** 1 neuer Test für `entity_data`-Merge elif-Pflicht (config_flow.py:346) — `test_config_flow_branch346_prefill`.
- **Test:** 16 neue Tests für Reconfigure-Flow, Schema-Helfer, Coordinator-Exception-Pfade, Sensor-Setup (`test_config_flow_reconfigure_detailed`, `test_coordinator`).
- **Test:** 6 neue Tests für `UemCurrentGenerationSensor` und `UemTotalLoadSensor` (`test_sensors_generation_load`).
- **Test:** 3 neue Tests für Thread-Pfad-Exceptions in `_compute_charge_limit` (`test_coordinator`).
- **Test:** Lifecycle-Tests für `async_setup_entry` und `async_unload_entry` (`test_init_setup_entry`).
- **Test:** `.gitignore` ergänzt `*.egg-info/`.
- **Release:** Alle 5 MVP-Akzeptanzfälle testbar; 328 Tests grün; Ruff clean; 99 % Coverage (2 provably-unreachable Branch-Parts: config_flow.py:346 field-not-in-prefill (durch Schema-All-Fields unmöglich), config_flow.py:486 do_rescan-false (durch vorherige if-Guards unmöglich)).

## 0.1.5 – Shadow-MVP-Abschluss: Testinfrastruktur, Incompleteness-Detection, Shadow-Safety

- **Bugfix:** Conftest-HA-Stub ersetzt keine echten HA-Module mehr (asyncio-Event-Loop-Konflikte behoben).
- **Bugfix:** Unload-Test nutzt asyncio.run für saubere Event-Loop-Isolation.
- **Bugfix:** `_is_incomplete` erkennt auch fehlende manual-capacity/power Keys von alten Einträgen → `Shadow – Einrichtung unvollständig` statt Absturz.
- **TDD:** 2 neue Tests für max-charge-power-missing-Szenario (MVP-Akzeptanzfall #5).
- **TDD:** 30+ Tests durch vollständigen HA-Stub in conftest (State, SensorEntity, FlowResult, dt_util, voluptuous).
- **Shadow-Safety:** AST-basierte Regressionstests verbieten HA-Service-Imports in jedem Shadow-Modul.
- **Release:** Alle 5 MVP-Akzeptanzfälle testbar abgedeckt; 271 Tests grün; Ruff clean; 94 % Coverage.

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
