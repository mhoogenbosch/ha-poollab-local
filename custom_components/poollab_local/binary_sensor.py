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

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import PoolLabCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PoolLab connectivity sensor."""
    coordinator: PoolLabCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]
    async_add_entities([PoolLabReachableSensor(coordinator, address)])


class PoolLabReachableSensor(BinarySensorEntity):
    """On when Home Assistant currently sees the PoolLab advertising.

    Deliberately not a CoordinatorEntity: this must reflect live Bluetooth
    presence, not the outcome of the last on-demand read.
    """

    _attr_has_entity_name = True
    _attr_name = "Bereikbaar"
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
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra

    async def async_update(self) -> None:
        """Check live Bluetooth presence and record how we reach the device."""
        self._present = bluetooth.async_address_present(
            self.hass, self._address, connectable=True
        )

        extra: dict[str, Any] = {
            "laatste_uitlezing_gelukt": self._coordinator.last_update_success,
        }

        service_info = bluetooth.async_last_service_info(
            self.hass, self._address, connectable=True
        )
        if service_info is not None:
            extra["signaalsterkte_dbm"] = service_info.rssi
            extra["ontvangen_via"] = _scanner_name(self.hass, service_info)

        self._extra = extra


def _scanner_name(hass: HomeAssistant, service_info: Any) -> str:
    """Human-readable name of the adapter/proxy that last heard the device."""
    source = getattr(service_info, "source", None)
    if not source:
        return "onbekend"
    try:
        scanner = bluetooth.async_scanner_by_source(hass, source)
    except Exception:  # noqa: BLE001 - helper availability varies per HA version
        scanner = None
    if scanner is not None:
        return getattr(scanner, "name", None) or str(source)
    return str(source)
