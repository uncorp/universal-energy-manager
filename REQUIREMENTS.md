# Lokaler allgemeiner Energiemanager – Arbeitsanforderungen

Stand: 2026-07-18. Dieses Dokument ist ein fachlicher Entwurf, keine laufende Steuerung.

## Projekt- und Veröffentlichungsentscheidung

- Der MVP-Umfang wurde am 2026-07-18 eingefroren. Neue Ideen bleiben im Backlog und werden erst nach stabiler Shadow-/Aktivvalidierung priorisiert.
- Bis dahin wird **kein** GitHub-Repository erstellt und nichts in Home Assistant produktiv installiert oder umgestellt.
- Nach Freigabe des MVP-Umfangs wird ein öffentliches GitHub-Projekt angelegt, das als HACS-Custom-Integration installierbar ist: **UEM – Universal Energy Manager**, Domain/Repository `universal_energy_manager` bzw. `universal-energy-manager`, Lizenz MIT.
- Der erste Release bleibt bewusst klein; Geräte, Tarife und Verbraucher werden später über Adapter erweitert.
- Neue Ideen werden fortlaufend als Anforderungen gesammelt, aber erst nach MVP und Shadow-/Aktivtest priorisiert. Release-Regel: zuerst notwendige Bugfixes und Regressionstests, danach nach Möglichkeit genau ein abgegrenztes neues Feature pro Version; sicherheitskritische Fehler können jederzeit als reiner Fix-Release erscheinen.

## Ziel

Ein lokaler, transparenter Energiemanager mit generischem Kern und gerätespezifischen Adaptern. Erster steuerbarer Adapter: E3DC über vorhandene Home-Assistant-/RSCP-Steuerung. Der Beobachtungs- und Verbraucherplanungsmodus unterstützt auch Anlagen ohne Hausakku, einschließlich BKW-only. Weitere Systeme werden nur über klar deklarierte Fähigkeiten angebunden.

Keine Cloud-Abhängigkeit, keine künstliche Helferflut und keine unverständlichen konkurrierenden Regelphasen.

## Prinzipien

1. **Messung vor Forecast:** Aktuelle Erzeugung, Netzleistung, SoC und Verbraucherleistung sind die Wahrheit. Forecasts planen vorsichtig, dürfen vorhandenen PV-Überschuss aber nicht blockieren.
2. **Endziel statt Zwischenziel:** Akkuladung wird gegen das echte Tages-/Reserveziel und das effektive Ladeende geplant, nicht gegen eine täglich ansteigende Zwischenzielrampe.
3. **Früh absichern, später freigeben:** Bei ausreichender PV und gefährdetem Ziel zuerst Akku-/Bedarf absichern; Restenergie danach an flexible Verbraucher.
4. **Nur ein Entscheider:** Akku, Wallboxen, Wärmepumpe und weitere steuerbare Verbraucher erhalten ihre Limits aus einem zentralen Plan, nicht aus konkurrierenden Einzelreglern.
5. **Jede Entscheidung erklärbar:** Entscheidungssensor mit Eingaben, Priorität, Sollwert und wirtschaftlicher Begründung.
6. **Fail-safe:** Bei Adapter-/Messfehlern keine gefährliche Aktion. Hardwareeigene Netz- und Schutzgrenzen bleiben aktiv.
7. **Nachweisbare Qualität:** UEM soll durch transparente Entscheidungen, robuste Tests, Shadow-Betrieb und reale Akzeptanzfälle besser werden — nicht durch unbelegte „AI“-Versprechen. Vor öffentlichem Release werden vergleichbare Systeme und ihre Stärken als Feature-/Testmatrix ausgewertet.
8. **Nutzervorgaben vor Optimierung:** Harte manuelle Gerätesperren, manuelle Zeitpläne und externe Regler haben Vorrang vor UEM. UEM erklärt die Unterbrechung sichtbar, statt diese Vorgaben zu überschreiben.

## Eingänge und interne Gruppen

### Netzanschluss und Messkonzept
- Genau ein kanonischer Netzanschlusspunkt (Import/Export) ist die physische Bilanz-Wahrheit; Quellen können z. B. Discovergy, Tibber Pulse, E3DC, iMSys oder ein anderer geeigneter Smart Meter sein.
- Die Einrichtung fragt nur das Messkonzept ab, nicht detaillierte Messorte einzelner Geräte: ein Zähler, separater Wärmepumpenzähler, Zählerkaskade oder PV-Erzeugungszähler.
- Mehrere Gesamt-Netzzähler werden niemals addiert. Bei Kaskaden wird der Hauptzähler für die Gesamtbilanz genutzt; Unterzähler dienen der Tarif-, Verbraucher- oder Kostenzuordnung.
- Bestehende Energy-Dashboard-Quellen werden bevorzugt erkannt und als Vorschlag angeboten. Eine detaillierte Sondertopologie bleibt später optional und ist kein MVP-Pflichtschritt.
- Jeder Zähler kann genau einer Tarifgruppe zugeordnet werden (z. B. Haushalt, Wärmepumpe, Wallbox/Auto). Der Manager verwendet für einen Verbraucher ausschließlich den Preis und die Zeitfenster seiner Tarifgruppe.
- Tarifgruppen unterstützen Standardtarif, dynamische 15-Minuten-Preise oder feste günstige/teure Zeitfenster. Stunden werden nur bei einem festen Zeitfenstertarif definiert; bei dynamischem Tarif kommen sie aus der Preisquelle.
- Pro Tarifgruppe wird schlicht gewählt: alle dahinterliegenden flexiblen Verbraucher steuern, nur ausgewählte Verbraucher steuern oder nur beobachten.

### Erzeuger
- Mehrere PV-Flächen/Wechselrichter, optional BHKW, Wind, Balkonkraftwerk oder andere Erzeuger; Hausakku ist nicht vorausgesetzt.
- Erzeuger haben unterschiedliche Planungsmodelle: Solar mit ausrichtungs-/sonnenstandsbezogener Kurve, Wind mit wetter- und unsicherheitsbehafteter Kurve, BHKW als thermisch/fahrplanabhängig steuerbarer Erzeuger mit Leistung, Laufzeit und Wärmebedarf. Ein BHKW oder Windrad wird nicht wie PV behandelt.
- Aktuelle Leistung je Erzeuger und Summenleistung.
- Tagesenergie und Forecast je Erzeuger, inklusive Forecast-Fehlerhistorie.
- Forecast als 15-Minuten-Kurve mit konservativer Untergrenze je Zeitfenster, nicht nur als Tages-kWh-Summe. Mehrere Forecast-Entitäten für unterschiedliche PV-Flächen und Ausrichtungen werden einzeln zugeordnet und intern summiert.
- Fehlt eine verwertbare Forecast-Kurve, weist die Integration darauf hin und fällt auf eine vorsichtige Live-PV-/Sonnenstandsstrategie zurück; sie erzwingt keinen bestimmten Cloud-Anbieter.
- Ein Balkonkraftwerk wird als Erzeuger modelliert, nie als negativer Verbraucher.

### Verbraucher
- Haus-Grundlast, Wärmepumpe, BWWP, Wallboxen und weitere steuerbare Verbraucher.
- Aktuelle Leistung und, falls vorhanden, Energie-/Statusentitäten.
- Summen: aktuelle Gesamtlast, geplanter Restbedarf, flexible Lasten.
- Alle Leistungswerte werden intern mit klarer Richtung normalisiert. Ein negativer Restlast-/Hausverbrauchssensor ist kein negativer Verbraucher, sondern muss über Netz- und Erzeugermesspunkt als Export bzw. nicht separat gemessene Erzeugung eingeordnet werden.

### Saisonale Notstromreserve
- Die feste Nutzer-Mindestreserve bleibt eine harte Untergrenze.
- Darüber liegt eine selbstlernende saisonale Reservekurve: am kürzesten Tag höher, am längsten Tag niedriger und zwischen diesen Punkten gleitend angepasst.
- Die konkrete Reserve berücksichtigt zusätzlich konservative PV-Kurve, erwarteten Nacht-/Hausbedarf und Datenvertrauen. Ihre Zusammensetzung bleibt als eine verständliche Diagnose sichtbar, nicht als Sammlung saisonaler Schalter.

### Geplante Netzausfallvorsorge
- Ein geplanter Netzausfall kann mit Start- und Endzeit eingegeben werden. Der Manager plant das gesamte Zeitfenster: Das Speicherziel zum Beginn deckt nur den erwarteten kritischen **Netto**bedarf bis zur jeweils erwarteten nutzbaren PV-Erzeugung plus Sicherheitsaufschlag, nicht pauschal einen vollen Akku.
- An einem sonnigen Vormittag bleibt dadurch gezielt freie Kapazität für spätere PV-Erzeugung erhalten. Bei winterlicher oder konservativ zu geringer PV-Prognose darf der Manager dagegen rechtzeitig ausreichend aus dem Netz vorladen, damit der kritische Grundbedarf während des gesamten Ausfallfensters gedeckt bleibt. Netzladung vor dem Ausfall erfolgt nur, wenn die Energie-/Leistungsrechnung dies erfordert.
- PV während eines Netzausfalls wird nur eingeplant, wenn der jeweilige Speicher-/Wechselrichteradapter bestätigte Inselbetriebsfähigkeit für diese PV-Quelle und die relevanten Verbraucher meldet; ohne diese Fähigkeit wird der PV-Forecast für die Ausfallzeit nicht als verfügbar angenommen.
- Speicher werden nicht pauschal gleichwertig gezählt. Jeder Adapter beschreibt seine Backup-Reichweite: keine Inselversorgung, einzelne Steckdosen, ausgewählte Stromkreise oder ganzes Haus. Nur Energie, die die relevanten kritischen Verbraucher tatsächlich versorgen kann, zählt zur jeweiligen Notstromreserve.
- Ein BKW-Speicher mit Inselsteckdose wird somit für die daran versorgten Verbraucher eingeplant, aber nicht fälschlich als Reserve für den gesamten Hausverbrauch behandelt.

### E3DC-Adapter und Zugangsdaten
- Der erste aktive Adapter verwendet die bereits konfigurierte HA-Integration `e3dc_rscp` (`torbennehmer/hacs-e3dc`) als lokale RSCP-Schicht und deren sicheren Services für Leistungsgrenzen.
- Die neue Integration fragt deshalb weder E3DC-IP noch Benutzername/Passwort erneut ab und speichert keinerlei E3DC-Zugangsdaten.
- IP, Zugangsdaten, Tokens, Diagnosedumps und Backups gehören niemals in das Git-Projekt, README, Beispielprofile oder Logs.
- `rscp2mqtt` ist kein MVP-Zwang: Es erfordert zusätzlich MQTT und einen laufenden Bridge-Dienst. Eine MQTT-Datenquelle kann später ein optionaler Adapter werden.

### Speicher
- Ein oder mehrere Speicher; jeder Speicher beschreibt SoC, nutzbare Kapazität, maximale Dauer-Lade-/Entladeleistung, ggf. nur kurzfristige Peak-Leistung, Lade-/Entladewirkungsgrad und verfügbare Steuerfunktionen.
- Topologie je Speicher/Erzeuger explizit: AC- oder DC-gekoppelt, kann aus Netz laden, kann einspeisen, eigene PV-Quelle und Messpunktumfang.
- Gerätespezifischer Adapter übersetzt generische Limits in sichere Gerätebefehle.
- Nicht steuerbare Speicher (z. B. BKW-Speicher ohne sichere Steuerentität) werden als beobachtete, autonome Energiequelle modelliert; der Manager erfindet dafür keine Regelbefehle.
- Bilanzierung verhindert Doppelzählung: Erzeuger-/Speicherleistung wird nur einmal am jeweils definierten Messpunkt in die Gesamtbilanz aufgenommen.

### Fahrzeuge und Wallboxen
- Verbindung, Ladeleistung, optional Fahrzeug-SoC und Ziel-SoC.
- Pro Fahrzeug: fehlende Energie, späteste Abfahrt, Priorität, Mindest-/Maximalleistung, Phasenfähigkeit.
- Mehrere Wallboxen werden gemeinsam geplant.
- Ein nicht verbundenes Fahrzeug mit verfügbarer SoC-Entität wird als **wahrscheinlicher, aber nicht harter Bedarf** berücksichtigt.

## Lernen aus Historie

- Lokale HA-Langzeitstatistiken, keine zusätzlichen Tages-/Monatshelfer.
- Zeitraster: 15 Minuten.
- Hauslast getrennt nach Werktag/Wochenende; robuste Median- und Sicherheitsquantile statt blindem Mittelwert.
- PV-Prognosen je Erzeuger mit saisonaler Fehlerkorrektur; Planung verwendet konservative Untergrenzen.
- Wiederkehrende, robuste Abweichungen nach Tageszeit/Sonnenstand (z. B. Morgen- oder Abendverschattung) korrigieren die jeweilige Erzeuger-Kurve. Kurzzeitige Wolken, einzelne Verschattungen und Messausreißer werden über robuste Zeitfenster/Medianwerte nicht als dauerhafte Lernregel übernommen.
- Die PV-Kurve steuert den Ladezeitpunkt: Ist die erwartete Erzeugung in den späteren Intervallen zu gering, wird Akku-/Fahrzeugbedarf früh geladen statt auf eine hohe Tages-kWh-Summe zu vertrauen.
- Fahrzeuge: Ansteckzeit, Abzugszeit, typische Session-Energie, Wochentag/Weekend und Vorhersagevertrauen.
- Unzureichende Datenbasis bleibt sichtbar; bis dahin konservative Standardwerte oder vom Nutzer gesetzte Startwerte.

## Dynamische Preise und Akku-Dispatch

- Tarife werden auf ein einheitliches 15-Minuten-Raster normalisiert (z. B. Tibber/aWATTar/Octopus oder feste Zeitfenster).
- Tarifadapter nutzen vorhandene HA-Integrationen und deren bereits eingerichtete Authentifizierung. Für Tibber wird die offizielle `tibber.get_prices`-Aktion als Quelle verwendet; die vom Anbieter gelieferte Intervallauflösung bleibt erhalten.
- Zusätzlich gibt es eine generische Preis-Kurven-Schnittstelle (`start`, `end`, `Preis`, `Währung`) für andere HA-Integrationen. Ein einzelner aktueller Preis ohne Zukunftskurve erlaubt nur eine eingeschränkte Echtzeitstrategie, keine echte Fahrplanoptimierung.
- Preisbewertung umfasst Preisbestandteile, Speicherverluste, Batterieverschleiß, Einspeisevergütung und erwartete spätere Preise.
- Akku in günstigen Zeiten nicht entladen, wenn das Aufheben der Energie für ein erwartetes teures Zeitfenster wirtschaftlich besser ist.
- Netzladung nur, wenn sie gegen konservative PV-/Last-/Fahrzeugplanung und Kostenrechnung vorteilhaft ist; standardmäßig deaktiviert, bis der Geräteadapter sichere Netzladung unterstützt.

## Einspeisebegrenzung / Abregelung

- Unterstützte Vorgaben: feste W-Grenze, Prozentwert mit klarer Bezugsgröße, Nulleinspeisung, Zeitplan oder externe dynamische Grenze.
- Intern immer als absolute erlaubte Netzexportleistung in Watt führen.
- Harte Netzgrenze bleibt bei E3DC/Wechselrichter; der Manager ist die langsamere Planungsebene.
- Bei realer Annäherung an die Netzgrenze und offenem Akku-/Lastpotenzial eigene künstliche Limits sofort anheben/freigeben.
- Keine zweite schätzende Abregelungslogik mit willkürlichem Trigger neben der Hardwaregrenze.
- Der Manager leitet selbstlernend eine **freie Speicherreserve für erwartete Abregelung** ab: z. B. sind zwischen 11:00 und 13:00 voraussichtlich 5 kWh oberhalb der zulässigen Einspeisung zu erwarten, versucht er bis dahin ungefähr 5 kWh Akku-Kapazität freizuhalten. Das ist kein Nutzerregler und keine feste Pauschale.
- Die Berechnung nutzt 15-Minuten-Kurven aus hoher PV-Annahme, erwarteter Hauslast und bereits eingeplanten flexiblen Verbrauchern sowie reale Akku-Ladeleistung. Wiederkehrende Muster werden gelernt; der Wert ist nur als erklärende Diagnose `sensor.energy_manager_abregelungspuffer_kwh` sichtbar. `0 kWh` bedeutet: kein erwarteter Freiraum nötig.

## § 14a EnWG

- Netzbetreiber-Steuerbefehl hat Vorrang vor allen lokalen Zielen.
- Ein EMS muss eine vom Netzbetreiber übermittelte gesamthafte Bezugsobergrenze für alle angeschlossenen steuerbaren Verbrauchseinrichtungen verteilen.
- Erkennung nur über eine autoritative Schnittstelle/Entität: z. B. EEBUS/Steuerbox, vom Geräteadapter bereitgestellte Leistungsgrenze oder explizit gemappte HA-Entität.
- Nicht aus gemessener Leistung raten: Das wäre nicht belastbar.
- Bei aktivem Signal: transparente Anzeige der externen Obergrenze und nachvollziehbare Leistungsverteilung auf Wallboxen, Wärmepumpe/BWWP usw.

## Flexible Verbraucher und PV-Überschuss

Jeder Verbraucher wird bewusst in einem von vier Modi eingebunden:

1. **Messen:** nur Leistung/Energie für Bilanz und Lernen.
2. **Empfehlen:** UEM zeigt günstiges Fenster bzw. PV-Überschuss, sendet aber keinen Befehl.
3. **Kooperativ:** UEM stellt geräteunabhängige Überschuss- und Zeitfenstersignale bereit; der Nutzer verbindet sie mit seiner eigenen HA-Automation.
4. **Direkt steuern:** nur mit einem sicheren, ausdrücklich aktivierten Geräteadapter und passenden Mindestlauf-/Komfortregeln.

- Verbraucher mit steuerbarer Leistungs-/Start-/Freigabeentität werden als flexible Lasten eingebunden.
- Reihenfolge und Grenzen pro Verbraucher: Priorität, Mindestlaufzeit, Mindestpause, Mindest-/Maximalleistung, Deadline/Komfortgrenze.
- BWWP: zunächst empfehlen/kooperativ; direkte Steuerung nur über geeignete Freigabe-/Leistungs-/Temperaturschnittstelle und mit Warmwasser-/Hygieneregeln.
- Wärmepumpe: im MVP keine direkte harte Ein-/Aus-Steuerung. Später ausschließlich über einen geeigneten Adapter wie SG Ready oder Hersteller-EMS und mit Schutz für Mindestlaufzeiten, Abtauen, Komfort und Heizkurve.
- Beispiele weiterer Lasten: mehrere Wallboxen, Heizstab, Poolpumpe.
- Überschuss wird erst nach Sicherheits-, Fahrzeug- und Akku-Zielen verteilt; reale Einspeisebegrenzung kann die Reihenfolge kurzfristig übersteuern.
- Universelle Automationsschnittstelle ohne Gerätebindung:
  - `sensor.uem_ueberschuss_jetzt_w`
  - `sensor.uem_ueberschuss_15min_w`, `..._30min_w`, `..._1h_w`, `..._2h_w`
  - Jeder Zeitfensterwert ist die voraussichtlich durchgehend verfügbare **Mindestleistung ab jetzt** nach Reserve, Akku-/Fahrzeugziel, Abregelungspuffer und bereits geplanten Lasten.
  - Dadurch setzt der Nutzer Schwellen selbst in seiner Automation, etwa: `ueberschuss_1h_w >= 2000` für einen 2-kW-Verbraucher mit einstündiger Laufzeit. Es entstehen keine festen 1.000-/2.000-/3.000-W-Entitäten pro Gerät.
  - Werte werden bei relevanten Live-Abweichungen neu berechnet; sie sind eine transparente Planungsprognose, keine physische Garantie.

## Urlaubsmodus

- Aktiv mit Start- und Enddatum; endet automatisch zum angegebenen Datum.
- Gewöhnliche Fahrzeug-Ansteck-/Abfahrtsprognosen werden im Urlaubsmodus nicht als erwartete harte oder weiche Bedarfe eingeplant.
- Hauslast verwendet ein separates, konservatives Urlaubsprofil statt des normalen Werktagsprofils.
- Reserve, Tagesziel und Netzladefreigabe bleiben als wenige explizite Urlaubsparameter sichtbar und können über `!` fest vorgegeben werden.
- Ohne explizite Freigabe keine rein profilbasierte Netzladung für abwesende Fahrzeuge.

## Minimaler Bedienumfang

Normale Einstellungen:
- Strategie: PV zuerst / Akku zuerst / günstigster Strom / ausgewogen
- Mindest-Notstromreserve
- Akku-Tagesziel und Ladeende
- Tarifquelle
- Fahrzeugziele/Abfahrten, falls bekannt
- Freigabe für Netzladung

Keine 60 sichtbaren Expertenregler.

## Einrichtung, automatische Erkennung und Bedienoberfläche

- Der Setup-Assistent fragt nur unvermeidbare Grundlagen ab: gewähltes Messkonzept, kanonischer Netzanschlusszähler, erkannte Geräte/Adapter und gewünschte Tarifgruppe.
- Bereits in Home Assistant vorhandene Energy-Dashboard-Quellen, Gerätefähigkeiten und sichere Standardwerte werden automatisch erkannt und nur zur Bestätigung vorgeschlagen.
- Einmalige bzw. selten veränderte technische Werte gehören nicht als sichtbare Number-/Switch-Entitäten ins Dashboard. Sie werden mit Quelle und Erkennungsstatus in ein lesbares Profil exportiert.
- Profilkonzept:
  - automatisch erkannte Werte als dokumentierte Vorschläge,
  - nutzerdefinierte Werte als überschreibungsfeste Einträge mit `!`,
  - keine automatische Überschreibung einer Nutzervorgabe,
  - Reload/Validierung ohne Integrations-Neueinrichtung.
- Die normale UI bleibt auf Strategie, Reserve, Tagesziel, Tarifquelle, Fahrzeugzielen und Netzladefreigabe beschränkt. Erweiterte Diagnose ist auf einer eigenen Seite bzw. im Profil verfügbar, nicht als Entitätenflut.
- Ein zentraler Status zeigt für die eigene Planung relevante Nutzervorgaben verständlich an, z. B. `E3DC-Entladesperre durch Nutzer` oder `Wallbox-Zeitplan aktiv`. Nicht eindeutig zuordenbare externe Steuerzustände verhindern die Aktivierung, bis der Nutzer die exklusive Steuerung ausdrücklich bestätigt hat.

## MVP-Abgrenzung und Akzeptanzfälle

### Erster MVP
- Ein lokaler HA-Energiemanager mit generischem Datenmodell, erstem E3DC-Steueradapter und einem kanonischen Netzanschlusszähler.
- Vorhandene HA-Entitäten liefern Live-Erzeugung, Netzfluss, SoC, Akku-Leistung und optional eine PV-Kurve; der MVP baut keine eigenen Wetter- oder Tarif-Cloud-Anbindungen.
- Neuplanung im 15-Minuten-Raster plus sofortige Neuberechnung bei relevanten Live-Ereignissen.
- Konservativer PV-Kurvenforecast bis Ladeende, echtes Endziel und Abregelungspuffer; keine Zwischenzielrampe.
- Tarifdaten können im MVP angezeigt bzw. vorbereitet werden, aber keine vollautomatische vorausplanende Netzladung oder Negativpreis-Arbitrage.
- E3DC-Akku-Lade-/Entladegrenzen sicher setzen und nach Fehlern freigeben; keine Netzladung ohne explizite Freigabe.
- Beobachtungsmodus für PV-only/BKW-only, ohne Steuerbefehle an nicht sicher steuerbare Geräte.
- Schlanke UI, Profil-/Override-Datei und Entscheidungserklärung.
- Zuerst verpflichtender Shadow-Modus bei jeder Neuinstallation: Der Manager berechnet und protokolliert seine **eigenen** Entscheidungen aus echten Live-Daten, sendet aber keine E3DC-Befehle.
- Aktive Steuerung kann erst nach einem sichtbaren Bereitschaftsbericht, einer bewussten Nutzerfreigabe und einer bestätigten exklusiven Steuerkonfiguration aktiviert werden.
- Nicht eindeutig zuordenbare externe Steuerzustände werden im Aktivierungsdialog ausdrücklich abgefragt; aktive Steuerung wird nie durch ein Update oder Lernen automatisch eingeschaltet.

### Bewusst nach dem MVP
- Mehrere Tarife/Zählerkaskaden als aktive Kostenoptimierung.
- 24-/48-Stunden-Preisplanung für Hausakku und Fahrzeuge, einschließlich negativer **all-in** Preise. Der Ziel-SoC am Beginn eines günstigen Fensters wird dabei so gewählt, dass Energie- *und* Leistungsaufnahme während des Fensters maximal sinnvoll möglich sind — nicht pauschal „Akku leer“.
- Preis-/Zeitfenster berücksichtigen erwartete Fahrzeugverbindung, Fahrzeugbedarf, Ladeleistung, PV-Kurve, Einspeisevergütung, Speicherverluste und Batterieverschleiß.
- Erhält ein verschiebbarer Verbraucher ein günstiges Zeitfenster, plant UEM die zugehörige Akku-Strategie gemeinsam: während eines wirtschaftlich günstigen Fensters Entladung sperren und, falls erforderlich sowie freigegeben, Hausakku vorladen. Die Empfehlung ist damit kein isolierter Gerätezeitpunkt.
- Bevor ein geplanter Zeitplan wirksam wird, zeigt UEM transparent `voraussichtlich aktiv: Netzladen 01:00–03:00`, `Entladesperre 00:45–03:15` und den Grund. Manuelle Sperren und Zeitpläne behalten Vorrang; ohne sichere Netzladefähigkeit bzw. explizite Freigabe bleibt es eine Empfehlung.
- Hausanschluss- und Phasenmodell für gleichzeitige flexible Lasten. Ein einmaliger Sicherungswert bzw. eine bestätigte Anschlussleistung ist eine harte Grenze; Beobachtungswerte können nur einen konservativen Mindesthinweis liefern, nie die Sicherung automatisch festlegen.
- Mehrere steuerbare Wallboxen, Wärmepumpe/BWWP und vollständige Verbraucher-Arbitrage.
- Direkte §14a-/EEBUS-Anbindung; im MVP nur vorbereitete externe Leistungsgrenze über vorhandene HA-Entität.
- Vollständige Fahrzeug-SoC-Adapter und Profillernen für abwesende Fahrzeuge.
- Gerätespezifische Adapter jenseits E3DC.

### Akzeptanzfälle
1. Unter Tagesziel und mit ausreichender PV: Der Akku erhält mindestens die zum echten Endziel benötigte Leistung; kein künstlich niedriger Zwischenziel-Korridor.
2. PV-Prognose fällt am Nachmittag: Der Manager lädt früher, statt auf die Tages-kWh-Summe zu vertrauen.
3. Vorhandene Tarifdaten: Preis-Kurve und Status sind sichtbar, aber im MVP werden daraus keine automatisch geplanten Netzlade- oder Entladesperrbefehle erzeugt.
4. Reale Einspeisung nähert sich der Hardwaregrenze: künstliche Akku-Begrenzung wird freigegeben, bevor PV ohne Not verloren geht.
5. Fehler/fehlende Messung: E3DC-Limits werden sicher freigegeben und der Status erklärt die Deaktivierung.

## Empfehlungen für verschiebbare Haushaltsgeräte

- UEM kann aus Erzeugungs-/Tarifkurve und gelerntem Grundbedarf Empfehlungen erzeugen, z. B. `Heute voraussichtlich 14 kWh freier PV-Überschuss – guter Zeitraum für Waschmaschine/Geschirrspüler: 11:30–14:00`.
- Bei sicherer winterlicher PV-Unterdeckung kann es später das günstigste zusammenhängende Preisfenster für die hinterlegte Laufzeit eines Geräts vorschlagen (z. B. drei Stunden).
- Standard ist Empfehlung, nie unbeaufsichtigtes automatisches Starten. Aktive Gerätesteuerung erfordert einen explizit als startbereit/freigegeben konfigurierten Adapter.

## Startwerte und Nutzer-Overrides

Optionales Textprofil im Projekt bzw. später im Integrationsspeicher:

```text
# Automatisch erkannt; wird als Vorschlag aktualisiert, solange kein !-Override existiert.
[detected]
grid_meter = "sensor.tibber_pulse_power"
battery.max_charge_w = 12000
battery.max_discharge_w = 12000
wallbox.garage.max_power_w = 11000

# Zahl = Startwert/lernbarer Prior
# !Zahl = harte Nutzervorgabe, darf vom Lernen nicht überschrieben werden
[preferences]
battery.reserve_pct = 25
battery.target_soc_pct = !95
vehicle.tesla.departure_h = 7.5
vehicle.tesla.energy_need_kwh = 18
```

Die Integration zeigt jede wirksame harte Vorgabe sichtbar an. Ungültige oder fehlende Werte werden nicht stillschweigend geschätzt.

## Eigene, wenige Entitäten

- `sensor.energy_manager_status`
- `sensor.energy_manager_entscheidung`
- `sensor.energy_manager_erzeugung_aktuell`
- `sensor.energy_manager_gesamtlast_aktuell`
- `sensor.energy_manager_restbedarf`
- `sensor.energy_manager_effektive_reserve`
- `sensor.energy_manager_tarif_prognose`
- `switch.energy_manager_aktiv`
- `select.energy_manager_strategie`

Erweiterte Diagnosen sind bei Bedarf abrufbar, aber nicht als Entitätenflut im Standard-Dashboard sichtbar.
