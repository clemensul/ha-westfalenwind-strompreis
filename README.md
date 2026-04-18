# Westfalenwind Strompreis (Home Assistant Custom Integration)

Diese Integration stellt den aktuell gueltigen Westfalenwind-Strompreis als Sensor bereit.
Die Daten werden aus einer festen REST-API geladen:
https://www.westfalenwind.de/?type=1772708565

## Funktionen

- Konfigurierbarer Abrufplan (Startzeit und Anzahl Updates pro Tag)
- Laden des kompletten Datensatzes als Forecast im Coordinator-Cache
- Automatisches Zusammenfassen benachbarter Intervalle mit identischem Preis
- Ermittlung des aktuell gueltigen 15-Minuten-Intervalls per UTC-Vergleich: start <= now < end
- Sensorwert ist price_ct_kwh in ct/kWh (aus dem geladenen Forecast abgeleitet)
- Robuste Fehlerbehandlung:
  - Netzwerk-/HTTP-Fehler => UpdateFailed
  - Kein passendes Intervall => None (kein harter Fehler)

## Sensor

- Name: Westfalenwind Strompreis
- Unique ID: westfalenwind_current_price
- Einheit: ct/kWh
- State Class: measurement
- Icon: mdi:lightning-bolt
- Zusaetzliche Attribute:
  - tariff_name
  - valid_from
  - valid_until
  - refresh_schedule

Zusatzsensor Forecast:

- Name: Westfalenwind Strompreis Forecast
- Unique ID: westfalenwind_price_forecast
- Einheit: ct/kWh
- Sensorwert: Preis des naechsten Intervalls
- Zusaetzliche Attribute:
  - forecast (komprimierter Datensatz mit echten Preiswechseln)
  - entries
  - refresh_schedule

Fuer den dynamischen Endpunkt werden dieselben zwei Sensoren bereitgestellt:

- Westfalenwind Dynamischer Strompreis
- Westfalenwind Dynamischer Strompreis Forecast

## Konfiguration

In der Integration koennen folgende Optionen gesetzt werden:

- fetch_time: Erste lokale Abrufzeit (Format HH:MM), Standard 00:01
- updates_per_day: Anzahl API-Abrufe pro Tag, Standard 24

## Installation (manuell)

1. Den Ordner custom_components in dein Home-Assistant-Config-Verzeichnis kopieren.
2. Home Assistant neu starten.
3. Integration ueber Einstellungen > Geraete und Dienste hinzufuegen.
4. Nach Westfalenwind suchen und Einrichtung bestaetigen.

## Installation ueber HACS

1. Repository als benutzerdefiniertes Repository in HACS hinzufuegen.
2. Kategorie Integration auswaehlen.
3. Westfalenwind Strompreis installieren.
4. Home Assistant neu starten.
5. Integration in der Oberflaeche hinzufuegen.
gt
## Testen im Devcontainer

1. Das Repository in VS Code oeffnen.
2. Reopen in Container ausfuehren.
3. Warten, bis `scripts/setup` Home Assistant installiert hat.
4. Home Assistant im Workspace-Root starten: `hass -c .`
5. Im Browser `http://localhost:8123` oeffnen und die Erstkonfiguration abschliessen.
6. Danach die Integration ueber Einstellungen > Geraete und Dienste hinzufuegen.
