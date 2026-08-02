# Changelog

All notable changes to this fork are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions
track upstream with an `-mh.N` suffix for fork releases.

## [2.2.0-mh.1] - 2026-08-02

### Added
- **`binary_sensor.poollab_shock_needed`** — a straight yes/no on whether the pool needs
  shocking, from combined chlorine against the 0.5 ppm target. Device class `problem`, so
  it presents as a warning.

  Its `advice` attribute states the reasoning in words, and covers the case where
  chloramines are fine but free chlorine is too low to disinfect — reporting only "no
  shocking needed" would be true and useless there.

  The sensor is **`unknown` rather than `off`** whenever combined chlorine cannot be
  determined. "No shock needed" and "I cannot tell" are different answers, and only one is
  safe to act on; in automations, trigger on the state becoming `on` rather than on
  "not off".

## [2.1.0-mh.1] - 2026-08-02

### Added
- **`sensor.poollab_combined_chlorine`** — chloramines, derived as total minus free
  chlorine. This is the value that tells you whether the pool needs shocking: chlorine
  already spent on contaminants, responsible for the "chlorine smell" and stinging eyes.
  Target is below 0.5 ppm.

  The sensor deliberately produces nothing when subtracting would be meaningless, and says
  so via `reason_unavailable`: when only one of the two was measured, when the readings are
  more than 15 minutes apart (total chlorine is meant to be measured seconds after free
  chlorine in the same cuvette), or when either reading is clamped because it was out of
  range. Measurement noise making free exceed total yields `0.0`, never a negative amount.
- **[docs/CHLORINE_CHEMISTRY.md](docs/CHLORINE_CHEMISTRY.md)** explaining the three chlorine
  values, how to read them together, why the sensor sometimes stays empty, and how chlorine
  interacts with pH, cyanuric acid and alkalinity. Inspired by the equivalent document in
  [stefanh12/Poollab](https://github.com/stefanh12/Poollab) (MIT), rewritten for this
  integration's local measurements.
- `tests/test_combined_chlorine.py` covering the pairing rules.

## [2.0.0-mh.1] - 2026-08-02

The integration is now bilingual (English/Dutch) and ready to share. **Breaking:** entity
names and several attribute keys changed.

### Changed
- **Entity names now come from the translation files** instead of being hardcoded, via
  `translation_key`. English and Dutch are included; other languages fall back to English.
  Entity IDs are unaffected — only display names change.
- **Attribute keys and values are English**, so automations are portable:
  - `genegeerde_meting` → `skipped_reading`, `genegeerde_meting_op` → `skipped_reading_at`
  - `waarde_is_ondergrens` → `value_is_minimum`
  - `meetbereik_min` / `meetbereik_max` → `range_min` / `range_max`
  - `ontvangen_via` → `received_via`, `signaalsterkte_dbm` → `rssi`,
    `in_bereik` → `in_range`, `adapter_id` → `source_id`,
    `laatste_uitlezing_gelukt` → `last_read_successful`, `geheugen_vol` → `memory_full`
  - `status`: `onder meetbereik` / `boven meetbereik` → `under_range` / `over_range`
  - `ideal_range_status`: `te laag` / `te hoog` → `low` / `high`
- Documentation, code comments and log messages translated to English.

## [1.1.1-mh.1] - 2026-08-02

### Fixed
- **Home Assistant could differ from the device display by 0.01.** Readings were rounded
  to the specified number of decimals while parsing, so a device value of 0.026 became
  `0.03` where the display shows `0.02` — the device truncates where we rounded. It also
  cost precision in long-term statistics. The raw device value is now stored and the
  decimal count moved to `suggested_display_precision` on the entity, so Home Assistant
  handles presentation. State keeps full precision; formatting is a display choice.

## [1.1.0-mh.1] - 2026-08-01

### Fixed
- **An overrange reading was taken as `0.0` and therefore judged "too low" — the exact
  opposite of reality.** On hardware the device turns out to report `0.0` on overrange as
  well: the reading simply did not fit its scale. A total alkalinity above 200 ppm showed
  as `0.0` with verdict `low`, so an automation acting on it would correct the wrong way.

  The value is now **clamped to the top of the measuring range**, reading as "at least
  this", flagged by the new `value_is_minimum` attribute. When no range is known for that
  parameter type, the reading is skipped rather than shown as `0.0`.
- `skipped_reading` now names the actual reason instead of always reporting underrange.

### Added
- Parser tests for overrange clamping and for leaving a normal reading untouched.

## [1.0.1-mh.1] - 2026-08-01

### Fixed
- **Two measuring ranges corrected.** The API documentation and the user manual
  contradict each other; the manual prints a scale bar per test and wins here.
  - **Total chlorine**: 0–0.60 → **0–8.00 ppm** (manual p. 32). The 0.60 cannot be right:
    a pool runs 1–3 ppm and free chlorine is listed as 0–6 in the same table.
  - **Total alkalinity**: 0–300 → **0–200 ppm** (manual p. 22). This shifts the threshold
    above which the device reports `OR`.

## [1.0.0-mh.1] - 2026-08-01

Every command in the official BLE API is now exposed; nothing in the protocol goes unused.

### Added
- **Sleep** (`SLEEP_DEVICE`, `0x04`): deep sleep immediately instead of waiting out the
  ~300 s auto-off. Draws under 20 µA, typically 8.5 µA.
- **Restart** (`RESET_DEVICE`, `0x03`).
- **Contrast up/down** (`0x08`/`0x09`): one LCD level within range 18–38. At the limit the
  device answers with result code `0x02`, treated as a normal outcome rather than an error.
- **LCD contrast sensor** with the last known level. Disabled by default: the protocol has
  no "read contrast" command, so the value is only known after a step.
- **Unit select** (`GET/SET_PPM_MGL`, `0x0A`/`0x0B`) switching between ppm and mg/L; the
  current setting is read during each poll.
- **Erase memory** (`RESET_MEASURES`, `0x06`). **Disabled by default** — irreversible, and
  without the cloud the device memory is the only copy.

### Fixed
- `RESET_DEVICE` and `SLEEP_DEVICE` produce **no response**; the device kills its radio at
  once. They bypass the normal command routine, which waits for a notification and would
  always time out. A failing write is documented as platform-dependent and expected, so it
  is logged at debug level rather than raised.

## [0.9.0-mh.1] - 2026-08-01

The official API documentation was read in full rather than relying on a transcription,
which surfaced data the device already sent but that was never shown.

### Added
- **`sensor.poollab_via_proxy`**: which Bluetooth adapter or proxy hears the device. In a
  multi-proxy setup this changes, and a read that keeps taking a weak route explains
  timeouts. Attributes: `in_range`, `rssi`, `source_id`.
- **`sensor.poollab_stored_measurements`**: `result_count` from `GET_INFO`, with
  `maximum` (256 = 16 flash cells × 16) and `memory_full`.
- **`sensor.poollab_clock_drift`**: device clock versus Home Assistant in seconds. The
  device timestamps its own measurements, so this shows when **Set clock** is due.
- **`range_min` / `range_max` attributes** per measurement sensor, from the official table
  "Measurement Result Types" (pp. 21–22). This explains why a reading falls out of range:
  pH is only measured between 6.50 and 8.40.
- **OEM variant** recognised from `active_id` (0=INTERNAL, 1=PoolLab 1.0,
  2=9-in-1 Multitest, 3=ISOLab 1.0, 4=Aquaviva, 5=FinWell Pro), set as the device model.

### Changed
- `device_info` and the proxy-name lookup extracted into shared helpers; that logic was
  duplicated across three classes.

## [0.8.0-mh.1] - 2026-08-01

### Changed
- **Failed measurements no longer overwrite the sensor value.** Measuring without a
  reagent tablet makes the photometer report underrange with value `0.0`, which used to
  drag the sensor from e.g. pH 7.2 down to 0.0 and pollute long-term statistics. Such
  readings are now skipped; the last valid measurement stays. Attributes `skipped_reading`
  and `skipped_reading_at` keep it visible.
- A parameter only ever measured as underrange still gets a sensor (without a value), so
  it is visible that it *was* measured.

### Added
- **Own integration logo.** The integration showed "Icon not available" under Settings →
  Devices & Services. Since Home Assistant 2026.3 a custom integration can ship its own
  brand images via the
  [brands proxy API](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/):
  `brand/icon.png` (256×256) and `brand/icon@2x.png` (512×512), no manifest change needed.
  A pull request to `home-assistant/brands` is no longer the route — that repository
  auto-closes PRs for `custom_integrations/*`.
- Icons for all entities: `mdi:ph` for pH, `mdi:test-tube` for other parameters, and the
  reachability sensor toggles between `mdi:bluetooth-connect` and `mdi:bluetooth-off`.

## [0.7.0-mh.1] - 2026-08-01

Diagnostics, so the log file is no longer needed to tell whether the device is reachable.

### Added
- **`binary_sensor.poollab_reachable`** (device class `connectivity`): shows live whether
  Home Assistant hears the device advertising. Deliberately not a `CoordinatorEntity` —
  it tracks current Bluetooth reception, not the outcome of the last read. Attributes:
  `received_via`, `rssi`, `last_read_successful`.
- **`sensor.poollab_signal_strength`**: RSSI of the last advertisement in dBm. Cleared
  once the device is out of range, so no stale value suggests it is still in reach.

## [0.6.0-mh.1] - 2026-08-01

First version confirmed on real hardware (PoolLab 1.0, MAC prefix `60:44:7A:`). A full
read takes 1.4–2.8 seconds over an ESPHome Bluetooth proxy.

### Added
- **Set clock button** (`PCMD_API_SET_TIME`, `0x02`). The device stamps every measurement
  with its own clock, so drift lands straight in `measured_at`. A fresh read follows
  automatically.
- Logo and banner (`images/`, self-contained SVG).
- README expanded into a full guide.

### Changed
- Connection setup extracted into `_connect()`, shared by reading and clock setting.

### Verified on hardware
- `GET_INFO` returns a correct battery level.
- `GET_MEASURES` decodes a real record correctly: parameter type 9 recognised as pH, plus
  sequence number, timestamp and status code.
- The pH fix from 0.5.0-mh.1 confirmed: no more "not a valid unit" warning.

## [0.5.0-mh.1] - 2026-08-01

First release of this fork, split from
[mf76130/ha-poollab-local](https://github.com/mf76130/ha-poollab-local) v0.4.1, which was
explicitly untested on hardware.

### Fixed
- **pH sensors logged a warning on every start.** They combined `device_class: ph` with
  unit `"pH"`, while Home Assistant accepts only `None` for that device class
  (`DEVICE_CLASS_UNITS[SensorDeviceClass.PH] == {None}`).
- **An implausible device clock aborted the entire read.** The `unix_time` field from
  `GET_INFO` is a uint64; an uninitialised or corrupt clock raised
  `OverflowError`/`OSError` from `datetime.fromtimestamp`, outside the `BleakError` and
  `TimeoutError` the coordinator catches.
- **Corrupt records could yield `nan` as a sensor value**, polluting long-term statistics.
  Non-finite floats are now skipped.

### Added
- **`measured_at`** attribute per measurement sensor. The device is only read on demand,
  so without a timestamp a reading from an hour ago is indistinguishable from one three
  weeks old.
- **Last measurement** sensor (`device_class: timestamp`) so automations can act on
  staleness.
- **`tests/test_parsers.py`**: offline validation of the frame parsers against synthetic
  protocol frames, covering the edge cases above. No hardware or HA runtime needed.

### Changed
- Target ranges (`IDEAL_RANGES`) replaced with common guidance figures for a private
  chlorine outdoor pool; upstream carried the values of one specific pool.
- Battery sensor marked as diagnostic.

[2.2.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v2.2.0-mh.1
[2.1.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v2.1.0-mh.1
[2.0.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v2.0.0-mh.1
[1.1.1-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v1.1.1-mh.1
[1.1.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v1.1.0-mh.1
[1.0.1-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v1.0.1-mh.1
[1.0.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v1.0.0-mh.1
[0.9.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.9.0-mh.1
[0.8.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.8.0-mh.1
[0.7.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.7.0-mh.1
[0.6.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.6.0-mh.1
[0.5.0-mh.1]: https://github.com/mhoogenbosch/ha-poollab-local/releases/tag/v0.5.0-mh.1
