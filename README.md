# UEM – Universal Energy Manager

A local-first Home Assistant energy manager for photovoltaic systems, home batteries and flexible loads.

UEM is developed with E3DC in mind and uses adapters so that other systems can follow. It plans from live energy flows and conservative 15-minute PV forecasts, explains every decision, and avoids cloud lock-in and configuration clutter.

## First release scope

The first release is deliberately small:

- `e3dc_rscp` as the E3DC data-source adapter
- real battery end target instead of artificial intermediate charge corridors
- optional multiple PV forecast curves
- conditional curtailment headroom
- mandatory Shadow mode on installation
- active control only after explicit user approval and an exclusive-controller check

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
6. The config flow discovers entities from your existing `e3dc_rscp` integration. Confirm the detected entities to create a Shadow-only entry.

**UEM does not store any E3DC credentials, IPs, or tokens.** It reuses the entity registry of your existing `e3dc_rscp` configuration entry.

### No-control boundary

The first release is **Shadow-only**: UEM reads sensor values and publishes planning output, but never calls a Home Assistant service to control hardware. The `switch.energy_manager_aktiv` entity is intentionally absent — active control will only appear in a future release after a deliberate user opt-in.

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

After installation UEM provides three read-only sensors:

| Entity name | Description |
|---|---|
| `sensor.energy_manager_status` | Current safety mode and health. State is `Shadow – keine aktive Steuerung` in normal operation. Attributes: `active_control` (always `false`), `commands_sent` (always `false`), `last_error` (null when healthy), `forecast_connected` (boolean). |
| `sensor.energy_manager_entscheidung` | Human-readable planning explanation. Shows whether live values are valid and whether the PV forecast is connected. |
| `sensor.energy_manager_soll_akku_ladelimit` | Calculated charge-limit setpoint in watts. Value is `0.0` in the current Shadow implementation because no control is applied. Attributes: `shadow_only` (`true`), `command_sent` (`false`). |

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
