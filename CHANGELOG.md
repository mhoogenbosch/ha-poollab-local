# Changelog

Alle noemenswaardige wijzigingen aan deze fork worden hier vastgelegd.

Het formaat volgt [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/),
en het versienummer volgt upstream met een `-mh.N`-suffix voor fork-releases.

## [0.9.0-mh.1] - 2026-08-01

De officiële API-documentatie ([BLE.pdf](https://poollab.org/static/api/BLE.pdf), v2)
is deze keer volledig uitgelezen in plaats van geleund op een transcriptie. Daaruit
kwamen een paar gegevens die het apparaat al meestuurde maar die nergens zichtbaar
waren.

### Added
- **`sensor.poollab_via_proxy`**: welke Bluetooth-adapter of -proxy het apparaat hoort.
  In een opstelling met meerdere proxy's wisselt dat, en een uitlezing die telkens over
  een zwakke route loopt verklaart timeouts. Attributen: `in_bereik`,
  `signaalsterkte_dbm` en `adapter_id`. De naam blijft staan als het apparaat uit gaat.
- **`sensor.poollab_opgeslagen_metingen`**: `result_count` uit `GET_INFO`, met attributen
  `maximum` (256 = 16 flashcellen × 16) en `geheugen_vol`.
- **`sensor.poollab_klokafwijking`**: verschil tussen de apparaatklok en Home Assistant
  in seconden. Het apparaat stempelt zijn metingen zelf, dus dit vertelt wanneer
  "Klok gelijkzetten" nodig is.
- **Attributen `meetbereik_min` / `meetbereik_max`** per meetsensor, uit de officiële
  tabel "Measurement Result Types" (pp. 21–22). Dit maakt inzichtelijk waarom een meting
  buiten bereik valt: pH meet het apparaat alleen tussen 6,50 en 8,40.
- **OEM-variant herkend** via `active_id` uit `GET_INFO` (0=INTERNAL, 1=PoolLab 1.0,
  2=9-in-1 Multitest, 3=ISOLab 1.0, 4=Aquaviva, 5=FinWell Pro). Wordt als model in het
  apparaatregister gezet; alle varianten delen dezelfde BLE-API.

### Changed
- `device_info` en het opzoeken van de proxynaam zijn uitgefactoreerd naar gedeelde
  helpers; die logica stond in drie klassen gekopieerd.

## [0.8.0-mh.1] - 2026-08-01

### Changed
- **Mislukte metingen overschrijven de sensorwaarde niet meer.** Meet je zonder
  reagenstablet, dan rapporteert de fotometer `underrange` met waarde `0.0`. Die
  liet de sensor eerder van bijvoorbeeld pH 7,2 naar 0,0 springen, wat ook de
  langetermijnstatistiek vervuilt. Zulke metingen worden nu overgeslagen bij het
  bepalen van de waarde; de laatste geldige meting blijft staan. **Overrange
  blijft wél gewoon de waarde**, want "hoger dan ik kan meten" is echte,
  actiegevende informatie — bijvoorbeeld bij chloor.
- Is er een genegeerde meting die recenter is dan de getoonde waarde, dan melden
  de attributen `genegeerde_meting` en `genegeerde_meting_op` dat, zodat een
  mislukte meting niet stilletjes verdwijnt.
- Wordt een parameter uitsluitend als underrange gemeten, dan krijgt hij alsnog
  een sensor (zonder waarde), zodat zichtbaar is dát er gemeten is.

### Added
- **Eigen integratielogo.** De integratie toonde "Icon not available" in
  Instellingen → Apparaten en diensten. Sinds Home Assistant 2026.3 kan een
  custom integration zijn merkafbeeldingen zelf meeleveren via de
  [brands proxy API](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/):
  `brand/icon.png` (256×256) en `brand/icon@2x.png` (512×512), zonder wijziging
  in `manifest.json`. Een pull request naar `home-assistant/brands` is daarvoor
  niet meer nodig — die repository sluit PR's voor `custom_integrations/*`
  inmiddels automatisch.
- Iconen voor alle entiteiten: pH krijgt `mdi:ph`, overige parameters
  `mdi:test-tube`, en de bereikbaarheidssensor wisselt tussen
  `mdi:bluetooth-connect` en `mdi:bluetooth-off`.
- Parsertest voor het behoud van de underrange-status.

## [0.7.0-mh.1] - 2026-08-01

Diagnostiek, zodat je niet meer in het logbestand hoeft te duiken om te weten of het
apparaat überhaupt bereikbaar is.

### Added
- **`binary_sensor.poollab_bereikbaar`** (device class `connectivity`): laat live zien
  of Home Assistant de PoolLab hoort adverteren. Bewust géén `CoordinatorEntity` — dit
  volgt de actuele Bluetooth-ontvangst, niet de uitkomst van de laatste uitlezing.
  Attributen: `ontvangen_via` (welke adapter of proxy), `signaalsterkte_dbm` en
  `laatste_uitlezing_gelukt`.
- **`sensor.poollab_signaalsterkte`**: RSSI van de laatste advertentie in dBm, met
  `ontvangen_via` als attribuut. Handig om te bepalen of er een proxy dichter bij het
  bad nodig is. Wordt leeggemaakt zodra het apparaat niet meer gezien wordt, zodat er
  geen verouderde waarde blijft staan die suggereert dat het nog in bereik is.
- README: uitleg over de bereikbaarheidssensor, en de twee foutwijzen zijn nu aan hun
  kenmerkende duur in het log te herkennen (0,000 s = apparaat uit; ~21 s = verbonden
  maar geen antwoord).

## [0.6.0-mh.1] - 2026-08-01

Eerste versie die op echte hardware is bevestigd (PoolLab 1.0, MAC-prefix `60:44:7A:`).
Een volledige uitlezing duurt 1,4–2,8 seconden via een ESPHome Bluetooth-proxy.

### Added
- **Knop "Klok gelijkzetten"** (`PCMD_API_SET_TIME`, commando `0x02`). Het apparaat
  stempelt elke meting met zijn eigen klok, dus drift daar komt rechtstreeks terug in
  het `measured_at`-attribuut. Na het zetten volgt automatisch een verse uitlezing.
- Logo en banner (`images/`, zelfstandige SVG's zonder externe afhankelijkheden).
- README uitgebreid tot een volledige handleiding: vergelijking met de
  cloud-integraties, vereisten voor de Bluetooth-proxy, entiteiten- en
  attributentabellen, automation-voorbeelden, een tabel voor probleemoplossing en een
  beschrijving van het protocol.

### Changed
- De verbindingsopzet is uitgefactoreerd naar `_connect()`, zodat uitlezen en
  klokinstellen dezelfde route delen.

### Verified on hardware
- `GET_INFO` levert een correct batterijniveau.
- `GET_MEASURES` ontleedt een echt meetrecord volledig juist: parametertype 9 herkend
  als pH, plus volgnummer, tijdstempel en statuscode. Een meting zonder reagenstablet
  komt terug als `measure_status` 1 → attribuut `status: "onder meetbereik"`, wat
  bevestigt dat ook het statusveld op de juiste offset gelezen wordt.
- De pH-fix uit 0.5.0-mh.1 is bevestigd: geen "not a valid unit"-waarschuwing meer.

## [0.5.0-mh.1] - 2026-08-01

Eerste release van de fork, afgesplitst van upstream
[mf76130/ha-poollab-local](https://github.com/mf76130/ha-poollab-local) v0.4.1.

### Fixed
- **pH-sensoren logden een waarschuwing bij elke start.** De pH-entiteiten
  combineerden `device_class: ph` met eenheid `"pH"`, terwijl Home Assistant
  voor die device class uitsluitend `None` accepteert
  (`DEVICE_CLASS_UNITS[SensorDeviceClass.PH] == {None}`). De eenheid wordt nu
  weggelaten voor pH; overige parameters houden `ppm`.
- **Een onzinnige apparaatklok liet de hele uitlezing klappen.** Het
  `unix_time`-veld uit `GET_INFO` is een uint64; een niet-geïnitialiseerde of
  corrupte klok gooide `OverflowError`/`OSError` uit `datetime.fromtimestamp`,
  buiten de `BleakError`/`TimeoutError` die de coordinator opvangt. De waarde
  wordt nu genegeerd in plaats van fataal.
- **Corrupte meetrecords konden `nan` als sensorwaarde opleveren**, wat de
  langetermijnstatistiek vervuilt. Niet-eindige floats worden overgeslagen.

### Added
- Attribuut **`measured_at`** per meetsensor: wanneer de meting daadwerkelijk
  op het apparaat is gedaan. Zonder dit is een waarde van een uur geleden niet
  te onderscheiden van een die drie weken oud is, omdat het apparaat alleen op
  afroep wordt uitgelezen.
- Sensor **"Laatste meting"** (`device_class: timestamp`) met het tijdstip van
  de meest recente meting, zodat automations op veroudering kunnen sturen
  ("al twee weken geen watertest gedaan").
- **`tests/test_parsers.py`**: offline validatie van de frame-parsers tegen
  synthetische protocolframes (GET_INFO en GET_MEASURES), inclusief de
  randgevallen hierboven. Draait zonder hardware en zonder HA-runtime.
- Nederlandse vertaling (`translations/nl.json`).

### Changed
- Interface vernederlandst: knop "Jetzt abrufen" → **"Nu ophalen"**,
  statuswaarden `zu niedrig`/`zu hoch` → **`te laag`**/**`te hoog`**,
  `underrange`/`overrange` → **`onder meetbereik`**/**`boven meetbereik`**,
  batterijsensor → **"Batterij"**.
- Batterijsensor gemarkeerd als `EntityCategory.DIAGNOSTIC`.
- Streefwaarden (`IDEAL_RANGES`) vervangen door gangbare richtwaarden voor een
  privé-buitenbad met chloor, aangevuld met broom en totale hardheid. Upstream
  had hier de waarden van één specifiek zwembad staan.

[0.9.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.9.0-mh.1
[0.8.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.8.0-mh.1
[0.7.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.7.0-mh.1
[0.6.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.6.0-mh.1
[0.5.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.5.0-mh.1
