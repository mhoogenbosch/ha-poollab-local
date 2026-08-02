"""Constants for the PoolLab Local integration.

All protocol details (UUIDs, command IDs, byte layouts, measurement types)
are taken from the official "PoolLab 1.0 Bluetooth API - Interface
Documentation" (Water-i.d. GmbH, version 2, 2022-03-02),
https://poollab.org/static/api/BLE.pdf
"""
from __future__ import annotations

DOMAIN = "poollab_local"

MANUFACTURER = "Water-i.d."
MODEL = "PoolLab 1.0"

# --- GATT profile ("PoolLabSvc") ---
SERVICE_UUID = "a7ee04a9-507b-4910-a528-b619d5501924"
CHAR_MISO_CMD_UUID = "2ff18b59-195d-4ee1-b78c-0cbde3eff9c2"     # read response data
CHAR_MOSI_CMD_UUID = "91bfa536-3036-4901-8813-3635fced7b90"     # write commands
CHAR_MISO_SIGNAL_UUID = "c2296c06-c7e0-4657-b42e-c8330826454c"  # notify: response ready

# --- Command framing ---
PREAMBLE = 0xAB

CMD_GET_INFO = 0x01
CMD_SET_TIME = 0x02
CMD_RESET_DEVICE = 0x03
CMD_SLEEP_DEVICE = 0x04
CMD_GET_MEASURES = 0x05
CMD_RESET_MEASURES = 0x06
CMD_SET_CONTRAST_PLUS = 0x08
CMD_SET_CONTRAST_MINUS = 0x09
CMD_GET_PPM_MGL = 0x0A
CMD_SET_PPM_MGL = 0x0B

DEVICE_MEMORY_SLOTS = 16 * 16  # 16 flash cells x 16 measurements

RESULT_OK = 0x01
RESULT_ERR = 0x02

# --- Timing ---
DEFAULT_TIMEOUT = 20  # seconds; BLE connect + command round trip can be slow

# No automatic background polling. The device only accepts one BLE
# connection at a time and is typically used a few times a week at most,
# so polling on a fixed schedule would just be needless Bluetooth traffic
# and a source of connection conflicts with the LabCom app. Use the
# "Fetch now" button entity right after taking a measurement instead.
UPDATE_INTERVAL_SECONDS: int | None = None

# Parameter type IDs referenced directly in code
TYPE_TOTAL_CHLORINE = 1
TYPE_FREE_CHLORINE = 8

# Combined chlorine (chloramines) = total - free. Per the user manual (p. 35)
# the device itself derives it that way. Target is as low as possible; above
# this the pool generally needs shocking.
COMBINED_CHLORINE_IDEAL_MAX = 0.5

# Free and total chlorine are measured in the same cuvette moments apart (DPD 3
# is added to the dissolved DPD 1). Subtracting readings from different sessions
# would be meaningless, so only pair them when taken close together.
COMBINED_CHLORINE_MAX_GAP_SECONDS = 15 * 60

# --- Measurement status codes (per flash_measurement_result.measure_status) ---
MEASURE_STATUS_OK = 0
MEASURE_STATUS_UNDERRANGE = 1
MEASURE_STATUS_OVERRANGE = 2

MEASURE_STATUS_NAMES = {
    MEASURE_STATUS_OK: "ok",
    MEASURE_STATUS_UNDERRANGE: "under_range",
    MEASURE_STATUS_OVERRANGE: "over_range",
}

IDEAL_RANGE_LOW = "low"
IDEAL_RANGE_HIGH = "high"
IDEAL_RANGE_OK = "ok"

# --- Target ranges for healthy pool water ---
# These are NOT part of the BLE protocol - the device only knows its own
# technical measuring range (see MEASUREMENT_RANGES below). The values here are
# common guidance figures for a private chlorine outdoor pool; adjust them to
# your own setup (salt water, bromine, spa).
IDEAL_RANGES: dict[int, tuple[float, float]] = {
    1: (1.0, 3.0),        # Total chlorine (ppm)
    6: (2.0, 4.0),        # Bromine (ppm)
    8: (1.0, 3.0),        # Free chlorine (ppm)
    9: (7.0, 7.4),        # pH
    10: (80.0, 120.0),    # Total alkalinity (ppm)
    11: (30.0, 50.0),     # Cyanuric acid / stabiliser (ppm)
    35: (200.0, 400.0),   # Total hardness (ppm)
}

# --- Configurable target ranges (options flow) ---
# Only the parameters people realistically tune. The key is stable storage; the
# type_id links it to a measurement. Anything not listed keeps its IDEAL_RANGES
# default and can be changed in const.py.
CONFIGURABLE_TARGETS: dict[str, int] = {
    "free_chlorine": 8,
    "total_chlorine": 1,
    "bromine": 6,
    "ph": 9,
    "alkalinity": 10,
    "cyanuric_acid": 11,
    "hardness": 35,
}

OPT_TARGETS = "targets"

# --- Measurement scenario types: type_id -> (name, unit, decimals) ---
# "ppm" is used as native_unit_of_measurement for all non-pH scenarios, matching
# the device's own unit naming in the API doc (mg/L mode is a device-side display
# toggle, not exposed separately here).
MEASUREMENT_TYPES: dict[int, tuple[str, str, int]] = {
    1: ("Total Chlorine", "ppm", 2),
    2: ("Ozone", "ppm", 2),
    3: ("Chlorine Dioxide", "ppm", 1),
    5: ("Active Oxygen", "ppm", 1),
    6: ("Bromine", "ppm", 1),
    7: ("Hydrogen Peroxide", "ppm", 2),
    8: ("Free Chlorine", "ppm", 2),
    9: ("pH", "pH", 2),
    10: ("Total Alkalinity", "ppm", 0),
    11: ("Cyanuric Acid", "ppm", 0),
    12: ("Hydrogen Peroxide HR", "ppm", 0),
    13: ("Total Hardness HR", "ppm", 1),
    14: ("Isothiazolinone", "ppm", 1),
    15: ("Nitrite LR", "ppm", 2),
    16: ("Nitrate", "ppm", 1),
    17: ("Phosphate", "ppm", 2),
    18: ("Iron LR", "ppm", 2),
    19: ("Dissolved Oxygen", "ppm", 2),
    20: ("Ammonia", "ppm", 2),
    21: ("Silica", "ppm", 2),
    22: ("Copper", "ppm", 2),
    23: ("Calcium", "ppm", 0),
    24: ("Ozone i.p.o. Chlorine", "ppm", 2),
    25: ("Magnesium", "ppm", 0),
    26: ("Potassium", "ppm", 1),
    27: ("pH HR", "pH", 2),
    28: ("pH LR", "pH", 2),
    29: ("pH HR (Saltwater)", "pH", 2),
    30: ("pH HR (Seawater)", "pH", 2),
    31: ("pH LR (Saltwater)", "pH", 2),
    32: ("pH LR (Seawater)", "pH", 2),
    33: ("pH MR (Saltwater)", "pH", 2),
    34: ("pH MR (Seawater)", "pH", 2),
    35: ("Total Hardness", "ppm", 0),
    36: ("pH MR", "pH", 2),
    37: ("Iodine", "ppm", 2),
    38: ("Urea", "ppm", 2),
    39: ("PHMB", "ppm", 0),
    40: ("Total Alkalinity (Seawater)", "ppm", 0),
    41: ("Total Chlorine (liquid)", "ppm", 2),
    42: ("Ozone (liquid)", "ppm", 2),
    43: ("Chlorine Dioxide (liquid)", "ppm", 2),
    44: ("Active Oxygen (liquid)", "ppm", 1),
    45: ("Bromine (liquid)", "ppm", 1),
    46: ("Hydrogen Peroxide (liquid)", "ppm", 2),
    47: ("Free Chlorine (liquid)", "ppm", 2),
    48: ("pH (liquid)", "pH", 2),
    49: ("Ozone i.p.o. Chlorine (liquid)", "ppm", 2),
}

# --- Technical measuring range of the device (type_id -> (min, max)) ---
# Based on the official API documentation, table "Measurement Result Types"
# (pp. 21-22). This is what the device can measure; a reading outside it makes
# the device report underrange or overrange itself. Not to be confused with
# IDEAL_RANGES, which are target values for the water.
#
# NOTE: on two points the API doc contradicts the user manual
# (poollab_manual_gb-fr-e-d-i.pdf), which prints a scale bar per test. The
# manual wins here, because it describes what the device actually measures:
#   - Total chlorine: API doc says 0.60, manual says 0-8.00 (p.32). 0.60 cannot
#     be right - a pool runs 1-3 ppm, and free chlorine is listed as 0-6.
#   - Total alkalinity: API doc says 300, manual says 0-200 (p.22).
MEASUREMENT_RANGES: dict[int, tuple[float, float]] = {
    1: (0.00, 8.00),   # manual p.32: 0-8.00 (API doc says 0.60 - typo)
    2: (0.00, 4.00),
    3: (0.00, 11.40),
    5: (0.00, 30.00),
    6: (0.00, 13.50),
    7: (0.00, 2.90),
    8: (0.00, 6.00),
    9: (6.50, 8.40),
    10: (0.00, 200.00),  # manual p.22: 0-200 (API doc says 300)
    11: (0.00, 160.00),
    12: (0.00, 200.00),
    13: (0.00, 500.00),
    14: (0.00, 200.00),
    15: (0.00, 1.65),
    16: (0.00, 50.00),
    17: (0.00, 1.50),
    18: (0.00, 1.00),
    19: (0.00, 10.00),
    20: (0.00, 1.30),
    21: (0.00, 6.00),
    22: (0.00, 5.00),
    23: (0.00, 500.00),
    24: (0.00, 4.00),
    25: (0.00, 100.00),
    26: (0.80, 12.00),
    27: (8.00, 9.30),
    28: (5.20, 6.80),
    29: (8.00, 9.30),
    30: (8.00, 9.30),
    31: (5.20, 6.80),
    32: (5.20, 6.80),
    33: (6.50, 8.40),
    34: (6.50, 8.40),
    35: (0.00, 200.00),
    36: (6.50, 8.40),
    37: (0.00, 21.47),
    38: (0.00, 2.51),
    39: (5.00, 60.00),
    40: (0.00, 200.00),
    41: (0.03, 8.00),
    42: (0.00, 4.07),
    43: (0.00, 11.42),
    44: (0.00, 30.00),
    45: (0.00, 13.55),
    46: (0.00, 2.90),
    47: (0.03, 8.00),
    48: (6.50, 8.40),
    49: (0.00, 4.07),
}

# --- OEM variants (active_id from GET_INFO) ---
# All variants share the same BLE API; they differ in which tests are
# available. Source: API documentation, "OEM Variants" (p. 23).
OEM_VARIANTS: dict[int, str] = {
    0: "INTERNAL",
    1: "PoolLab 1.0",
    2: "9-in-1 Multitest",
    3: "ISOLab 1.0",
    4: "Aquaviva",
    5: "FinWell Pro",
    6: "INTERNAL",
}
