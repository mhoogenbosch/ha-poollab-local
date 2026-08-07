"""The device keeps local wall-clock time, not UTC.

Reading its timestamps as real UTC put every measurement off by the local UTC
offset - two hours ahead in CEST, so a reading taken at 12:04 showed as 14:04.
No hardware or Home Assistant runtime needed.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

COMPONENT = Path(__file__).resolve().parent.parent / "custom_components/poollab_local"

# Pull the two helpers out of coordinator.py without importing Home Assistant.
src = (COMPONENT / "coordinator.py").read_text()
start = src.index("def device_time_to_utc")
end = src.index("class PoolLabCoordinator")
ns = {"datetime": datetime, "timezone": timezone, "tzinfo": type(timezone.utc)}
exec(compile(src[start:end], "coordinator.py", "exec"), ns)
device_time_to_utc = ns["device_time_to_utc"]
utc_to_device_time = ns["utc_to_device_time"]

AMS = ZoneInfo("Europe/Amsterdam")
failures = []


def check(label, got, want):
    ok = got == want
    print(f"  {'✅' if ok else '❌'} {label}: {got!r}" + ("" if ok else f"  (verwacht {want!r})"))
    if not ok:
        failures.append(label)


print("Zomertijd (CEST, UTC+2) — het geval dat de bug blootlegde:")
# Device shows 12:04:49 local. It encodes that as if it were UTC.
encoded = int(datetime(2026, 8, 7, 12, 4, 49, tzinfo=timezone.utc).timestamp())
got = device_time_to_utc(encoded, AMS)
check("12:04 lokaal -> 10:04 UTC", got, datetime(2026, 8, 7, 10, 4, 49, tzinfo=timezone.utc))
check("weergegeven in lokale tijd blijft 12:04",
      got.astimezone(AMS).strftime("%H:%M:%S"), "12:04:49")

print("\nWintertijd (CET, UTC+1) — offset moet meebewegen:")
enc_w = int(datetime(2026, 1, 15, 9, 30, 0, tzinfo=timezone.utc).timestamp())
check("09:30 lokaal -> 08:30 UTC", device_time_to_utc(enc_w, AMS),
      datetime(2026, 1, 15, 8, 30, tzinfo=timezone.utc))

print("\nSchrijven en teruglezen moet rondlopen:")
moment = datetime(2026, 8, 7, 10, 17, 48, tzinfo=timezone.utc)
check("set -> get geeft hetzelfde moment",
      device_time_to_utc(utc_to_device_time(moment, AMS), AMS), moment)
check("UTC-tijdzone: geen verschuiving",
      device_time_to_utc(utc_to_device_time(moment, timezone.utc), timezone.utc), moment)

print("\nRandgevallen:")
check("0 -> None", device_time_to_utc(0, AMS), None)
check("None -> None", device_time_to_utc(None, AMS), None)
check("onzinnige klok -> None", device_time_to_utc(2**63, AMS), None)

print("\n" + ("❌ MISLUKT: " + ", ".join(failures) if failures else "✅ Alle tijdcontroles geslaagd"))
sys.exit(1 if failures else 0)
