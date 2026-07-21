# UEM – Universal Energy Manager

A local-first Home Assistant energy manager for photovoltaic systems, home batteries and flexible loads.

UEM works with **any** home energy system that provides the required HA sensor entities. `e3dc_rscp` is **optional** and, when available, only provides auto-detected entity suggestions. Forecast.Solar is **optional** and provides as many Solar/PV forecasts as configured (roofs, orientations, balcony systems). BHKW and wind forecasts are not implemented in this release.

## First release scope

The first release is deliberately small:

- Universal entity mapping (any source, not just `e3dc_rscp`)
- Optional `e3dc_rscp` adapter for automatic entity suggestions
- Optional Forecast.Solar integration for multiple Solar/PV forecasts
- Real battery end target instead of artificial intermediate charge corridors
- Conditional curtailment headroom
- Mandatory Shadow mode on installation
- Active control only after explicit user approval and an exclusive-controller check

Dynamic tariff optimisation, EV scheduling, heat pumps and further adapters are planned after a stable Shadow release.

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
6. The config flow discovers entities from your existing `e3dc_rscp` integration if available. Confirm the detected entities (they are editable suggestions) to create a Shadow-only entry.
7. If `e3dc_rscp` is not installed, the flow offers manual entity mapping — UEM works with any system providing the required sensor entities.

**UEM does not store any E3DC credentials, IPs, or tokens.** When `e3dc_rscp` is present, it reuses the entity registry of your existing `e3dc_rscp` configuration entry. For manual mapping, you enter entity IDs directly.

### Reconfigure action

After installation, open the UEM config entry in **Settings → Devices & Services** and select **Reconfigure**. This re-discovers entities from any connected adapter (e.g. a newly installed `e3dc_rscp`) while preserving your existing manual mappings as suggestions — it never overwrites values you have set.

**No-control boundary**

The first release is **strictly sensor-only and Shadow-only**: UEM reads sensor values and publishes planning output, but never calls a Home Assistant service to control hardware. It adds **no switches, selects, services or controllable entities**. Active control can only be considered in a future release after deliberate user opt-in and an exclusive-controller check.

## Required source entities

UEM needs the following sensor categories from your existing `e3dc_rscp` integration. The config flow maps them automatically; no private entity IDs appear in documentation or this README.

| UEM input | Source key in `e3dc_rscp` | Description |
|---|---|---|
| Battery SoC | `soc` | Current state of charge (percent) |
| PV power | `solar-production` | Current PV generation (W) |
| House consumption | `house-consumption` | Current home load (W) |
| Grid export | `grid-production` | Current grid feed-in (W) |
| Battery charge | `battery-charge` | Current battery charge/discharge (W) |
| Battery capacity | `system-battery-installed-capacity` | Total installed battery capacity |
| Max charge power | `system-battery-charge-max` | Maximum battery charge power |
| PV forecast (optional) | any forecast entity with 15-min intervals | 15-minute PV generation curve |

All power values are normalised to watts. If a required entity is missing or unavailable, UEM reports a `Messdatenfehler` (measurement data error) and does not produce planning output.

## Shadow-mode sensors

After installation UEM provides five read-only sensors:

| Entity name | Description |
|---|---|
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
