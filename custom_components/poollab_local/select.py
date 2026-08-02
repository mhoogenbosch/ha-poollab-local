"""Select platform for PoolLab Local — the device's unit display mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, OEM_VARIANTS
from .coordinator import PoolLabCoordinator

UNIT_PPM = "ppm"
UNIT_MGL = "mg/L"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PoolLab unit-mode select."""
    coordinator: PoolLabCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]
    async_add_entities([PoolLabUnitModeSelect(coordinator, address)])


class PoolLabUnitModeSelect(CoordinatorEntity[PoolLabCoordinator], SelectEntity):
    """Switches the device display between ppm and mg/L (PCMD_API_SET_PPM_MGL).

    This is a device-side display setting; it does not change the values Home
    Assistant records, which stay in the unit the API reports them in.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "unit_mode"
    _attr_icon = "mdi:beaker-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = [UNIT_PPM, UNIT_MGL]

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator)
        self._address = address
        self._attr_unique_id = f"{address}_unit_mode"

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
        # Stay usable while the device is asleep, like the buttons: tying this
        # to the last poll would make it impossible to change once unreachable.
        return True

    @property
    def current_option(self) -> str | None:
        return (self.coordinator.data or {}).get("device_info", {}).get("unit_mode")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_unit_mode(mg_per_litre=option == UNIT_MGL)
