"""Button platform for PoolLab Local — manually trigger a BLE refresh."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import PoolLabCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PoolLab refresh button."""
    coordinator: PoolLabCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]
    async_add_entities(
        [
            PoolLabRefreshButton(coordinator, address),
            PoolLabSetTimeButton(coordinator, address),
            PoolLabSleepButton(coordinator, address),
            PoolLabRestartButton(coordinator, address),
            PoolLabContrastUpButton(coordinator, address),
            PoolLabContrastDownButton(coordinator, address),
            PoolLabEraseMemoryButton(coordinator, address),
        ]
    )


class PoolLabRefreshButton(CoordinatorEntity[PoolLabCoordinator], ButtonEntity):
    """Connects to the PoolLab right now and pulls the latest measurements.

    Use this right after taking a measurement instead of waiting for the
    (intentionally long) background poll interval - the device only
    accepts one BLE connection at a time, so polling rarely makes more
    sense than polling on demand.
    """

    _attr_has_entity_name = True
    _attr_name = "Nu ophalen"
    _attr_icon = "mdi:bluetooth-transfer"
    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator)
        self._address = address
        self._attr_unique_id = f"{address}_refresh_button"

    @property
    def available(self) -> bool:
        # Critical: never tie this to coordinator.last_update_success.
        # If a refresh attempt fails, the *only* way to retry is this
        # button - making it unavailable after a failed poll would create
        # a permanent deadlock (no auto-polling, no working retry button).
        return True

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.data or {}).get("device_info", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={("bluetooth", self._address)},
            name="PoolLab",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=str(info.get("fw_version", "")) or None,
        )

    async def async_press(self) -> None:
        """Trigger an immediate BLE poll of the device."""
        await self.coordinator.async_request_refresh()


class PoolLabSetTimeButton(PoolLabRefreshButton):
    """Sets the device clock to Home Assistant's current time.

    The PoolLab stamps every measurement with its own clock, so drift there
    lands straight in the `measured_at` attribute of each sensor.
    """

    _attr_name = "Klok gelijkzetten"
    _attr_icon = "mdi:clock-check-outline"
    _attr_device_class = None
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_set_time_button"

    async def async_press(self) -> None:
        """Send PCMD_API_SET_TIME with the current time."""
        await self.coordinator.async_set_device_time()


class PoolLabSleepButton(PoolLabRefreshButton):
    """Sends the device into deep sleep, as if holding the power button.

    Saves battery after a read: the device draws under 20 uA asleep, versus
    staying awake for its ~300 second auto-off timer.
    """

    _attr_name = "Slaapstand"
    _attr_icon = "mdi:power-sleep"
    _attr_device_class = None
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_sleep_button"

    async def async_press(self) -> None:
        await self.coordinator.async_sleep_device()


class PoolLabRestartButton(PoolLabRefreshButton):
    """Restarts the device."""

    _attr_name = "Herstarten"
    _attr_icon = "mdi:restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_restart_button"

    async def async_press(self) -> None:
        await self.coordinator.async_reset_device()


class PoolLabContrastUpButton(PoolLabRefreshButton):
    """Raises the LCD contrast one level (device range 18-38)."""

    _attr_name = "Contrast omhoog"
    _attr_icon = "mdi:brightness-7"
    _attr_device_class = None
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_contrast_up"

    async def async_press(self) -> None:
        await self.coordinator.async_step_contrast(increase=True)


class PoolLabContrastDownButton(PoolLabRefreshButton):
    """Lowers the LCD contrast one level (device range 18-38)."""

    _attr_name = "Contrast omlaag"
    _attr_icon = "mdi:brightness-5"
    _attr_device_class = None
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_contrast_down"

    async def async_press(self) -> None:
        await self.coordinator.async_step_contrast(increase=False)


class PoolLabEraseMemoryButton(PoolLabRefreshButton):
    """Erases every stored measurement on the device.

    Disabled by default: this is irreversible and wipes the device's entire
    measurement history, which is the only copy when you don't use the cloud.
    """

    _attr_name = "Geheugen wissen"
    _attr_icon = "mdi:database-remove"
    _attr_device_class = None
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_erase_memory"

    async def async_press(self) -> None:
        await self.coordinator.async_reset_measures()
