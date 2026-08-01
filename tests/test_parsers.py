"""Offline validation of the PoolLab frame parsers against the documented protocol.

Builds synthetic GET_INFO / GET_MEASURES responses byte-for-byte per the spec
in PROTOCOL.md and checks the coordinator decodes them correctly. No hardware,
no Home Assistant runtime needed - homeassistant.* is stubbed out.
"""
import struct
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

COMPONENT = Path(__file__).resolve().parent.parent / "custom_components/poollab_local"


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


class _Dummy:
    def __init__(self, *a, **k):
        pass

    def __class_getitem__(cls, item):
        return cls


class UpdateFailed(Exception):
    pass


# --- Minimal stand-ins for the imports coordinator.py pulls in -------------
_stub("bleak")
_stub("bleak.backends")
_stub("bleak.backends.device", BLEDevice=_Dummy)
_stub("bleak.exc", BleakError=type("BleakError", (Exception,), {}))
_stub(
    "bleak_retry_connector",
    BleakClientWithServiceCache=_Dummy,
    establish_connection=lambda *a, **k: None,
)
_stub("homeassistant")
_stub("homeassistant.components", bluetooth=_Dummy)
_stub("homeassistant.components.bluetooth", async_ble_device_from_address=lambda *a, **k: None)
_stub("homeassistant.core", HomeAssistant=_Dummy)
_stub(
    "homeassistant.helpers.update_coordinator",
    DataUpdateCoordinator=_Dummy,
    UpdateFailed=UpdateFailed,
)
_stub("homeassistant.helpers")

sys.path.insert(0, str(COMPONENT.parent))
import importlib.util

spec = importlib.util.spec_from_file_location("plc", COMPONENT / "coordinator.py")
plc = importlib.util.module_from_spec(spec)
sys.modules["plc"] = plc
# const.py is imported as a relative import; register it under the package name
const_spec = importlib.util.spec_from_file_location("const", COMPONENT / "const.py")
const = importlib.util.module_from_spec(const_spec)
const_spec.loader.exec_module(const)
plc.__package__ = ""
sys.modules["const"] = const
source = (COMPONENT / "coordinator.py").read_text().replace("from .const import", "from const import")
exec(compile(source, "coordinator.py", "exec"), plc.__dict__)

Coordinator = plc.PoolLabCoordinator

failures = []


def check(label, got, want):
    ok = got == want
    print(f"  {'✅' if ok else '❌'} {label}: {got!r}" + ("" if ok else f"  (verwacht {want!r})"))
    if not ok:
        failures.append(label)


# --- GET_INFO -------------------------------------------------------------
# preamble B0 | active_id B1-2 | fw B3-4 | result_count B5-6 |
# device time B7-14 (8 bytes) | mac B15-20 | battery B21-22
print("GET_INFO frame:")
measured_clock = int(datetime(2026, 8, 1, 10, 30, tzinfo=timezone.utc).timestamp())
info_frame = (
    bytes([0xAB])
    + struct.pack("<HHH", 1234, 260, 3)
    + measured_clock.to_bytes(8, "little")
    + bytes([0x60, 0x44, 0x7A, 0x11, 0x22, 0x33])
    + struct.pack("<H", 87)
).ljust(250, b"\x00")

info = Coordinator._parse_info(info_frame)
check("active_id", info["active_id"], 1234)
check("fw_version", info["fw_version"], 260)
check("result_count", info["result_count"], 3)
check("mac_address", info["mac_address"], "60:44:7A:11:22:33")
check("battery_level", info["battery_level"], 87)
check("device_time", info["device_time"], datetime(2026, 8, 1, 10, 30, tzinfo=timezone.utc))

# Implausible clock must not blow up the poll
bad_clock = bytes([0xAB]) + struct.pack("<HHH", 1, 1, 0) + b"\xff" * 8 + b"\x00" * 6 + struct.pack("<H", 50)
check("onzinnige klok -> None", Coordinator._parse_info(bad_clock.ljust(250, b"\x00"))["device_time"], None)

# --- GET_MEASURES ---------------------------------------------------------
# preamble, then 8 x 16-byte records:
# measure_id B0-1 | type B2 | status B3 | timestamp B4-7 | float value B8-11 | reserved B12-15
print("\nGET_MEASURES frame:")
stamp = int(datetime(2026, 7, 30, 14, 5, tzinfo=timezone.utc).timestamp())


def record(mid, mtype, status, ts, value):
    return struct.pack("<HBBIf", mid, mtype, status, ts, value) + b"\x00" * 4


body = (
    record(1, 9, 0, stamp, 7.31)          # pH
    + record(2, 8, 0, stamp + 60, 1.42)   # Free Chlorine
    + record(3, 10, 2, stamp + 120, 240.0)  # Total Alkalinity, overrange
    + struct.pack("<HBBIf", 4, 9, 0, stamp + 180, float("nan")) + b"\x00" * 4  # corrupt
)
frame = (bytes([0xAB]) + body).ljust(250, b"\x00")

records = [r for r in Coordinator._parse_measurements(frame) if r]
check("aantal geldige records (NaN geweerd)", len(records), 3)
check("pH-waarde", records[0]["value"], 7.31)
check("pH-type", records[0]["name"], "pH")
check("vrij chloor", records[1]["value"], 1.42)
check("timestamp record 1", records[0]["timestamp"], stamp)
check("status overrange", records[2]["status"], 2)
check("lege helft -> 0 records", len([r for r in Coordinator._parse_measurements(bytes([0xAB]) + b"\x00" * 128) if r]), 0)

print("\n" + ("❌ MISLUKT: " + ", ".join(failures) if failures else "✅ Alle parsercontroles geslaagd"))
sys.exit(1 if failures else 0)
