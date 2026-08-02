"""The PoolLab Local integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import CONFIGURABLE_TARGETS, DOMAIN, IDEAL_RANGES, OPT_TARGETS
from .coordinator import PoolLabCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PoolLab Local from a config entry."""
    address = entry.data[CONF_ADDRESS]
    coordinator = PoolLabCoordinator(hass, address)
    coordinator.ideal_ranges = _resolve_targets(entry)

    # Re-read the ranges when the user changes them in the options flow.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward platforms first, *then* attempt an initial refresh - and
    # don't let a failed refresh block setup. The device is often out of
    # range or asleep between measurements, and the "Nu ophalen" button
    # plus restored sensor state cover that gap. Gating setup on a
    # successful BLE connection (as async_config_entry_first_refresh does)
    # would make the whole integration - including the button - unusable
    # whenever the device simply isn't reachable right now.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_refresh()

    return True


def _resolve_targets(entry: ConfigEntry) -> dict[int, tuple[float, float]]:
    """User-configured target ranges layered over the built-in defaults."""
    ranges = dict(IDEAL_RANGES)
    for key, pair in (entry.options.get(OPT_TARGETS) or {}).items():
        type_id = CONFIGURABLE_TARGETS.get(key)
        if type_id is None or not pair or len(pair) != 2:
            continue
        ranges[type_id] = (float(pair[0]), float(pair[1]))
    return ranges


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload so every sensor picks up the new target ranges."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
