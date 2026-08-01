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
# "Nu ophalen" button entity right after taking a measurement instead.
UPDATE_INTERVAL_SECONDS: int | None = None

# --- Measurement status codes (per flash_measurement_result.measure_status) ---
MEASURE_STATUS_OK = 0
MEASURE_STATUS_UNDERRANGE = 1
MEASURE_STATUS_OVERRANGE = 2

MEASURE_STATUS_NAMES = {
    MEASURE_STATUS_OK: "ok",
    MEASURE_STATUS_UNDERRANGE: "onder meetbereik",
    MEASURE_STATUS_OVERRANGE: "boven meetbereik",
}

IDEAL_RANGE_LOW = "te laag"
IDEAL_RANGE_HIGH = "te hoog"
IDEAL_RANGE_OK = "ok"

# --- Streefwaarden (ideale range voor gezond zwemwater) ---
# Deze horen NIET bij het officiele BLE-protocol - het apparaat kent alleen
# zijn eigen technische meetbereik (zie MEASUREMENT_TYPES hieronder).
# Onderstaande waarden zijn gangbare richtwaarden voor een prive-buitenbad
# met chloor; pas ze aan op de eigen situatie (zoutbad, bromide, spa).
IDEAL_RANGES: dict[int, tuple[float, float]] = {
    1: (1.0, 3.0),        # Totaal chloor (ppm)
    6: (2.0, 4.0),        # Broom (ppm)
    8: (1.0, 3.0),        # Vrij chloor (ppm)
    9: (7.0, 7.4),        # pH
    10: (80.0, 120.0),    # Totale alkaliniteit (ppm)
    11: (30.0, 50.0),     # Cyanuurzuur / stabilisator (ppm)
    35: (200.0, 400.0),   # Totale hardheid (ppm)
}

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

# --- Technisch meetbereik van het apparaat (type_id -> (min, max)) ---
# Basis: de officiele API-documentatie, tabel "Measurement Result Types"
# (pp. 21-22). Dit is wat het apparaat kan meten; ligt een meting hierbuiten
# dan rapporteert het zelf underrange of overrange. Niet te verwarren met
# IDEAL_RANGES, dat zijn de streefwaarden voor het water.
#
# LET OP: op twee punten wijkt de API-doc af van de gebruikershandleiding
# (poollab_manual_gb-fr-e-d-i.pdf), die per test een schaalbalk met het bereik
# toont. De handleiding is hier leidend, want die beschrijft wat het apparaat
# daadwerkelijk meet:
#   - Totaal chloor: API-doc 0,60 vs handleiding 0-8,00 (p.32). 0,60 kan niet
#     kloppen - een zwembad voert 1-3 ppm, en vrij chloor staat op 0-6.
#   - Totale alkaliniteit: API-doc 300 vs handleiding 0-200 (p.22).
MEASUREMENT_RANGES: dict[int, tuple[float, float]] = {
    1: (0.00, 8.00),   # handleiding p.32: 0-8,00 (API-doc zegt 0,60 - typefout)
    2: (0.00, 4.00),
    3: (0.00, 11.40),
    5: (0.00, 30.00),
    6: (0.00, 13.50),
    7: (0.00, 2.90),
    8: (0.00, 6.00),
    9: (6.50, 8.40),
    10: (0.00, 200.00),  # handleiding p.22: 0-200 (API-doc zegt 300)
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

# --- OEM-varianten (active_id uit GET_INFO) ---
# Alle varianten delen dezelfde BLE-API; ze verschillen in welke tests
# beschikbaar zijn. Bron: API-documentatie, "OEM Variants" (p. 23).
OEM_VARIANTS: dict[int, str] = {
    0: "INTERNAL",
    1: "PoolLab 1.0",
    2: "9-in-1 Multitest",
    3: "ISOLab 1.0",
    4: "Aquaviva",
    5: "FinWell Pro",
    6: "INTERNAL",
}
