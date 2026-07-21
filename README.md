# UEM – Universal Energy Manager

A local-first Home Assistant energy manager for photovoltaic systems, home batteries and flexible loads.

UEM is developed with E3DC in mind and uses adapters so that other systems can follow. It plans from live energy flows and conservative 15-minute PV forecasts, explains every decision, and avoids cloud lock-in and configuration clutter.

## First release scope

The first release is deliberately small:

- **Universal entity mapping** — UEM works with any HA sensors; no adapter required
- `e3dc_rscp` as an **optional** E3DC data-source adapter for auto-discovery and prefill
- Optional Forecast.Solar integration — **Solar/PV only**, unlimited sources (d roofs, orientations, BKW)
- Reconfigure action — rescan adapter without overwriting manual values
- Real battery end target instead of artificial intermediate charge corridors
- Conditional curtainment headroom
- Mandatory **Shadow mode** on installation
- Active control only after explicit user approval and an exclusive-controller check
- **Reconfigure action** for adapter rescan without overwriting manual values

BHKW/Wind forecasts are out of scope for this release. Dynamic tariff optimisation, EV scheduling, heat pumps and further adapters are planned after a stable Shadow release.

## Safety

**Shadow mode only calculates from observed data and never sends commands.** Active control remains blocked until explicit user approval and an exclusive-control check succeed.

> This project is experimental energy-management software. Verify decisions in Shadow mode before enabling any active control.

## Installation

### HACS (Home Assistant Community Store)

1. In HACS, open **Integrations** → the three-dot menu → **Custom repositories**.
2. Enter the repository URL of this project and set the **Category** to `Integration`.
3. Find **UEM – Universal Energy Manager** in the list and install it.
4. After installation, restart Home Assistant.
5. Open **Settings → Devices & Services → Add Integration** and search for **UEM**.

### Universal setup flow

UEM is designed to work **without any adapter**:

1. The config flow detects whether an `e3dc_rscp` integration exists.
2. **No adapter found?** You see two options:
   - **Cancel** — set up the E3DC-RSCP integration first (recommended for E3DC users)
   - **Continue** — proceed with universal manual entity mapping
3. **Adapter found?** Detected entities are shown as editable prefill; you can accept, modify, or switch to manual mapping.
4. Confirm the entity assignments to create a Shadow-only UEM entry.

**UEM does not store any E3DC credentials, IPs, or tokens.** It reuses the entity registry of your existing configuration when available.

### No-control boundary

The first release is **strictly sensor-only and Shadow-only**: UEM reads sensor values and publishes planning output, but never calls a Home Assistant service to control hardware. It adds **no switches, selects, services or controllable entities**. Active control can only be considered in a future release after deliberate user opt-in and an exclusive-controller check.

## Required source entities

UEM needs the following sensor categories from Home Assistant. The config flow maps them automatically via the `e3dc_rscp` adapter when available; otherwise you assign them manually. No private entity IDs appear in documentation.

|| UEM input | Source key in `e3dc_rscp` | Description |
|---|---|---|---|
| Battery SoC | `soc` | Current state of charge (percent) |
| PV power | `solar-production` | Current PV generation (W) |
| House consumption | `house-consumption` | Current home load (W) |
| Grid export | `grid-production` | Current grid feed-in (W) |
| Battery charge | `battery-charge` | Current battery charge/discharge (W) |
| Battery capacity | `system-battery-installed-capacity` | Total installed battery capacity |
| Max charge power | `system-battery-charge-max` | Maximum battery charge power |
| PV forecast (optional) | any forecast entity with 15-min intervals | 15-minute PV generation curve |

All power values are normalised to watts. If a required entity is missing or unavailable, UEM reports a `Messdatenfehler` (measurement data error) and does not produce planning output.

## Forecast.Solar

Forecast.Solar is **optional** and supports **unlimited sources** (dächer, Ausrichtungen, BKW). Only Solar/PV forecasts are processed. BHKW and Wind forecasts are not implemented in this release.

## Reconfigure action

After installation, UEM provides a reconfigure action in the integration settings. This allows:

- **Rescan e3dc_rscp** — detect new/discovered entities without overwriting existing manual assignments
- **Edit entities** — modify the manual entity mapping without recreating the entry

Manual values are never silently overwritten.

## Shadow-mode sensors

After installation UEM provides five read-only sensors:

|| Entity name | Description |
|---|---|---|
| `sensor.energy_manager_status` | Current safety mode and health. State is `Shadow – keine aktive Steuerung` in normal operation. Attributes: `active_control` (always `false`), `commands_sent` (always `false`), `last_error` (null when healthy), `forecast_connected` (boolean). |
| `sensor.energy_manager_entscheidung` | Human-readable planning explanation. Shows whether live values are valid and whether the PV forecast is connected. |
| `sensor.energy_manager_soll_akku_ladelimit` | Calculated charge-limit setpoint in watts. The value reflects the planner's computed limit (may be `0.0` when live data is missing or the final target is already reached). Attributes: `shadow_only` (`true`), `command_sent` (`false`). |
| `sensor.energy_manager_erzeugung_aktuell` | Current PV generation power in watts, read from the mapped E3DC source. |
| `sensor.energy_manager_gesamtlast_aktuell` | Current household load in watts, read from the mapped E3DC source. |

## Development and tests

The local Home Assistant test dependency is deliberately isolated in `.venv-ha`; it is not a Home Assistant installation and cannot change a running HA instance. Create it with Python 3.11 and run the reproducible test command:

```bash
python3.11 -m venv .venv-ha
.venv-ha/bin/python -m pip install -r requirements_test.txt
bash scripts/run_tests.sh
```

`requirements_test.txt` pins Home Assistant to `2024.3.3`, matching CI. Do not use the lightweight `.venv` for the integration suite; it intentionally does not contain Home Assistant.

## Privacy

UEM is local-first. Never commit Home Assistant configuration, E3DC credentials, IP addresses, diagnostics, backups or real household energy data. Tests use synthetic fixtures only.

## License

MIT. See [LICENSE](LICENSE).
