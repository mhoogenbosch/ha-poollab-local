"""Binary sensor platform for PoolLab Local — is the device reachable right now?

The PoolLab powers itself off after roughly 300 seconds, so most of the time it
is simply not there. Without this, the only way to find out whether a failed
read meant "switched off" or "connected but silent" is to read the debug log.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    COMBINED_CHLORINE_IDEAL_MAX,
    COMBINED_CHLORINE_MAX_GAP_SECONDS,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    OEM_VARIANTS,
    TYPE_FREE_CHLORINE,
    TYPE_TOTAL_CHLORINE,
)
from .coordinator import PoolLabCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PoolLab connectivity sensor."""
    coordinator: PoolLabCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]
    async_add_entities(
        [
            PoolLabReachableSensor(coordinator, address),
            PoolLabShockNeededSensor(coordinator, address),
        ]
    )


class PoolLabShockNeededSensor(CoordinatorEntity[PoolLabCoordinator], BinarySensorEntity):
    """Whether the pool needs shocking, based on combined chlorine.

    Chloramines above the target mean the chlorine present is largely spent:
    it no longer disinfects but does cause the smell and irritation. Shocking
    breaks them down.

    Stays `unknown` rather than `off` when it cannot tell. "No shock needed"
    and "I have no idea" are different answers, and only one of them is safe
    to act on.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "shock_needed"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator)
        self._address = address
        self._attr_unique_id = f"{address}_shock_needed"

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.data or {}).get("device_info", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={("bluetooth", self._address)},
            name="PoolLab",
            manufacturer=MANUFACTURER,
            model=OEM_VARIANTS.get(info.get("active_id"), MODEL),
            sw_version=str(info.get("fw_version", "")) or None,
        )

    @property
    def available(self) -> bool:
        # Stay available so the state can be `unknown` with its `advice`
        # attribute intact. Inheriting CoordinatorEntity.available would make
        # the entity `unavailable` after any failed read - and the device is
        # switched off most of the time, so that would be its normal state.
        return True

    @property
    def icon(self) -> str:
        return "mdi:flash-alert" if self.is_on else "mdi:water-check"

    def _combined(self) -> tuple[float, dict, dict] | None:
        """Combined chlorine, only when the two readings genuinely pair up."""
        measurements = (self.coordinator.data or {}).get("measurements", {})
        free = measurements.get(TYPE_FREE_CHLORINE)
        total = measurements.get(TYPE_TOTAL_CHLORINE)
        if not free or not total:
            return None
        if free.get("clamped") or total.get("clamped"):
            return None
        if abs(total["timestamp"] - free["timestamp"]) > COMBINED_CHLORINE_MAX_GAP_SECONDS:
            return None
        return max(0.0, total["value"] - free["value"]), free, total

    @property
    def is_on(self) -> bool | None:
        result = self._combined()
        if result is None:
            return None
        combined, _free, _total = result
        return combined > COMBINED_CHLORINE_IDEAL_MAX

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self._combined()
        if result is None:
            return {
                "advice": "unknown - measure free and total chlorine in one session",
            }

        combined, free, total = result
        attrs: dict[str, Any] = {
            "combined_chlorine": round(combined, 2),
            "free_chlorine": free["value"],
            "threshold": COMBINED_CHLORINE_IDEAL_MAX,
        }
        if combined > COMBINED_CHLORINE_IDEAL_MAX:
            attrs["advice"] = (
                f"shock the pool - {combined:.2f} ppm chloramines, "
                f"above the {COMBINED_CHLORINE_IDEAL_MAX} ppm target"
            )
        elif free["value"] < 1.0:
            # No chloramine problem, but too little chlorine to disinfect;
            # saying only "no shock needed" would be misleading here.
            attrs["advice"] = (
                f"no shocking needed, but free chlorine is only "
                f"{free['value']:.2f} ppm - add chlorine"
            )
        else:
            attrs["advice"] = "no shocking needed"
        return attrs


class PoolLabReachableSensor(BinarySensorEntity):
    """On when Home Assistant currently sees the PoolLab advertising.

    Deliberately not a CoordinatorEntity: this must reflect live Bluetooth
    presence, not the outcome of the last on-demand read.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "reachable"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = True

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        self._coordinator = coordinator
        self._address = address
        self._attr_unique_id = f"{address}_reachable"
        self._present = False
        self._extra: dict[str, Any] = {}

    @property
    def device_info(self) -> DeviceInfo:
        info = (self._coordinator.data or {}).get("device_info", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={("bluetooth", self._address)},
            name="PoolLab",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=str(info.get("fw_version", "")) or None,
        )

    @property
    def is_on(self) -> bool:
        return self._present

    @property
    def icon(self) -> str:
        return "mdi:bluetooth-connect" if self._present else "mdi:bluetooth-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra

    async def async_update(self) -> None:
        """Check live Bluetooth presence and record how we reach the device."""
        self._present = bluetooth.async_address_present(
            self.hass, self._address, connectable=True
        )

        extra: dict[str, Any] = {
            "last_read_successful": self._coordinator.last_update_success,
        }

        service_info = bluetooth.async_last_service_info(
            self.hass, self._address, connectable=True
        )
        if service_info is not None:
            extra["rssi"] = service_info.rssi
            extra["received_via"] = _scanner_name(self.hass, service_info)

        self._extra = extra


def _scanner_name(hass: HomeAssistant, service_info: Any) -> str:
    """Human-readable name of the adapter/proxy that last heard the device."""
    source = getattr(service_info, "source", None)
    if not source:
        return "unknown"
    try:
        scanner = bluetooth.async_scanner_by_source(hass, source)
    except Exception:  # noqa: BLE001 - helper availability varies per HA version
        scanner = None
    if scanner is not None:
        return getattr(scanner, "name", None) or str(source)
    return str(source)
