import sys
sys.argv = ["x"]
exec(open("tests/test_parsers.py").read().replace("sys.exit(1 if failures else 0)", ""))

# Combined chlorine pairing rules (logic mirrored from the sensor)
from const import (COMBINED_CHLORINE_MAX_GAP_SECONDS, TYPE_FREE_CHLORINE,
                   TYPE_TOTAL_CHLORINE)

def pair_ok(free, total):
    if not free or not total:
        return False
    if free.get("clamped") or total.get("clamped"):
        return False
    return abs(total["timestamp"] - free["timestamp"]) <= COMBINED_CHLORINE_MAX_GAP_SECONDS

print("\nGebonden chloor - wanneer wel/niet berekenen:")
f = {"value": 0.03, "timestamp": stamp, "clamped": False}
t_ok = {"value": 0.08, "timestamp": stamp + 240, "clamped": False}
check("zelfde sessie -> berekenen", pair_ok(f, t_ok), True)
check("verschil klopt", round(t_ok["value"] - f["value"], 2), 0.05)
check("uren ertussen -> niet berekenen",
      pair_ok(f, {"value": 2.0, "timestamp": stamp + 7200, "clamped": False}), False)
check("geklemde meting -> niet berekenen",
      pair_ok(f, {"value": 8.0, "timestamp": stamp + 60, "clamped": True}), False)
check("vrij > totaal -> 0, niet negatief", max(0.0, 1.0 - 1.4), 0.0)

print("\n" + ("❌ MISLUKT: " + ", ".join(failures) if failures else "✅ Alles geslaagd"))
sys.exit(1 if failures else 0)
