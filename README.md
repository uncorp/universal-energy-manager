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

Shadow mode only calculates from observed data and never sends commands. Active control remains blocked until explicit user approval and an exclusive-control check succeed.

> This project is experimental energy-management software. Verify decisions in Shadow mode before enabling any active control.

## Installation

HACS installation instructions will be added with the first installable Shadow release.

## Privacy

UEM is local-first. Never commit Home Assistant configuration, E3DC credentials, IP addresses, diagnostics, backups or real household energy data. Tests use synthetic fixtures only.

## License

MIT. See [LICENSE](LICENSE).
