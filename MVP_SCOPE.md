# UEM MVP – eingefrorener Umfang

**Status:** Eingefroren am 2026-07-18. Neue Ideen gehen in das Backlog und verändern diesen Umfang nicht ohne bewusste Entscheidung nach der Shadow-/Aktivvalidierung.

## Ziel

Ein lokaler Home-Assistant-Energiemanager, der `e3dc_rscp` als Datenquellen-Adapter nutzt und die E3DC-Akkuladung gegen das echte Tagesziel und die PV-Kurve plant — ohne künstliche Zwischenzielrampe oder Entitätsflut.

## E3DC-Anbindung

- `e3dc_rscp` ist Pflicht und wird nicht neu implementiert.
- UEM erkennt die E3DC-RSCP-Entitäten standardmäßig über den zugehörigen Home-Assistant-Config-Entry und dokumentierte E3DC-RSCP-Sensorzuordnungen.
- Erkannte Entitäten werden im Setup vorbefüllt und zur Bestätigung angezeigt; bei fehlenden oder unplausiblen Werten wird nicht geraten und keine aktive Steuerung erlaubt.
- UEM speichert keine E3DC-IP, keine Zugangsdaten und keine Tokens.

## Enthalten

- Ein kanonischer Netzleistungsmesser.
- E3DC SoC, Batterie-, PV-, Haus- und Netzleistung aus `e3dc_rscp`.
- Mehrere vorhandene PV-Forecast-Entitäten mit 15-Minuten-Kurve; keine eigene Forecast-Cloud.
- Echtes Tagesziel, effektives Ladeende und konservative PV-Kurve.
- Bedingte freie Speicherreserve für erwartete Abregelung.
- Saisonale Notstromreserve als Basislogik.
- Pure, testbare Planungslogik und redigierte Testfixtures.
- Schlanke Status-/Entscheidungsentitäten und Profil-/Override-Konzept.
- Verpflichtender Shadow-Modus bei Installation.
- Aktive Steuerung erst nach expliziter Freigabe und Prüfung auf bekannte parallele Regler.
- E3DC-Limits bei sauberem UEM-Stopp freigeben, wenn E3DC erreichbar ist.

## Nicht enthalten

- Automatische 24-/48-Stunden-Preisplanung, Netzladen oder Negativpreis-Arbitrage.
- Aktive Wallbox-, Wärmepumpen-, BWWP- oder Haushaltsgerätesteuerung.
- Mehrere aktive Tarifgruppen/Zählerkaskaden.
- Direkte §14a-/EEBUS-Anbindung.
- Vollständige Fahrzeug-SoC-/Ankunftsprognose.
- Direkte RSCP- oder MQTT/rscp2mqtt-Anbindung.
- Aktive Planung geplanter Netzausfälle.

## Akzeptanzfälle

1. Unter Tagesziel lädt UEM gegen das echte Endziel, nicht gegen ein Zwischenziel.
2. Bei geringer später PV-Prognose lädt UEM früher.
3. Tarifdaten können sichtbar sein, führen aber im MVP nicht zu automatischen Zeitplänen.
4. Nähert sich reale Einspeisung der Hardwaregrenze, wird eine künstliche Akku-Begrenzung rechtzeitig freigegeben.
5. Bei fehlenden, alten oder unplausiblen Daten sendet UEM keine neuen E3DC-Befehle und erklärt den Status.
