# Changelog

Alle noemenswaardige wijzigingen aan deze fork worden hier vastgelegd.

Het formaat volgt [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/),
en het versienummer volgt upstream met een `-mh.N`-suffix voor fork-releases.

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

[0.5.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.5.0-mh.1
