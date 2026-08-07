"""Sensor platform for PoolLab Local."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    EntityCategory,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get as async_get_entity_registry,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    COMBINED_CHLORINE_IDEAL_MAX,
    COMBINED_CHLORINE_MAX_GAP_SECONDS,
    DEVICE_MEMORY_SLOTS,
    DOMAIN,
    IDEAL_RANGE_HIGH,
    IDEAL_RANGE_LOW,
    IDEAL_RANGE_OK,
    IDEAL_RANGES,
    MANUFACTURER,
    MEASUREMENT_TYPES,
    MEASURE_STATUS_NAMES,
    MEASUREMENT_RANGES,
    MODEL,
    OEM_VARIANTS,
    TYPE_FREE_CHLORINE,
    TYPE_TOTAL_CHLORINE,
)
from .coordinator import PoolLabCoordinator, device_time_to_utc


def _as_utc(timestamp: int | None) -> datetime | None:
    """Device timestamp to real UTC.

    The device keeps local wall-clock time, so the raw number must be shifted
    by the local UTC offset - see device_time_to_utc.
    """
    return device_time_to_utc(timestamp, dt_util.DEFAULT_TIME_ZONE)


def _device_info(coordinator: PoolLabCoordinator, address: str) -> DeviceInfo:
    """Shared device registry entry for every PoolLab entity."""
    info = (coordinator.data or {}).get("device_info", {})
    model = OEM_VARIANTS.get(info.get("active_id"), MODEL)
    return DeviceInfo(
        identifiers={(DOMAIN, address)},
        connections={("bluetooth", address)},
        name="PoolLab",
        manufacturer=MANUFACTURER,
        model=model,
        sw_version=str(info.get("fw_version", "")) or None,
    )


def _scanner_name(hass: HomeAssistant, source: Any) -> str | None:
    """Human-readable name of the adapter/proxy behind a Bluetooth source id."""
    if not source:
        return None
    try:
        scanner = bluetooth.async_scanner_by_source(hass, source)
    except Exception:  # noqa: BLE001 - helper availability varies per HA version
        scanner = None
    if scanner is not None:
        return getattr(scanner, "name", None) or str(source)
    return str(source)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PoolLab sensors from a config entry."""
    coordinator: PoolLabCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]

    known_types: set[int] = set()
    entities: list[SensorEntity] = [
        PoolLabBatterySensor(coordinator, address),
        PoolLabLastMeasurementSensor(coordinator, address),
        PoolLabSignalSensor(coordinator, address),
        PoolLabProxySensor(coordinator, address),
        PoolLabStoredResultsSensor(coordinator, address),
        PoolLabClockDriftSensor(coordinator, address),
        PoolLabContrastSensor(coordinator, address),
        PoolLabCombinedChlorineSensor(coordinator, address),
    ]

    # Recreate a sensor for every measurement type ever seen on this device
    # (from the entity registry), not just types present in the live
    # coordinator data right now. Otherwise, after a restart where the
    # device hasn't been read yet this session, these sensors would never
    # be instantiated at all - and RestoreEntity can't restore a value for
    # an entity object that doesn't exist.
    prefix = f"{address}_measure_"
    registry = async_get_entity_registry(hass)
    for entity_entry in async_entries_for_config_entry(registry, entry.entry_id):
        if not entity_entry.unique_id.startswith(prefix):
            continue
        try:
            type_id = int(entity_entry.unique_id[len(prefix) :])
        except ValueError:
            continue
        if type_id not in known_types:
            known_types.add(type_id)
            entities.append(PoolLabMeasurementSensor(coordinator, address, type_id))

    async_add_entities(entities)

    @callback
    def _add_new_measurement_sensors() -> None:
        if not coordinator.data:
            return
        # Include types seen only as underrange: those readings are not used as
        # a value, but the user should still see that the parameter was measured.
        seen_types = {
            *coordinator.data.get("measurements", {}),
            *coordinator.data.get("skipped", {}),
        }
        new_entities = [
            PoolLabMeasurementSensor(coordinator, address, type_id)
            for type_id in seen_types
            if type_id not in known_types
        ]
        for entity in new_entities:
            known_types.add(entity.type_id)
        if new_entities:
            async_add_entities(new_entities)

    _add_new_measurement_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_measurement_sensors))


class PoolLabBaseEntity(CoordinatorEntity[PoolLabCoordinator], RestoreEntity):
    """Common device info for all PoolLab entities.

    Combines CoordinatorEntity (live BLE data) with RestoreEntity, so the
    last known value survives a Home Assistant restart and isn't lost just
    because the device happens to be unreachable for the first poll after
    startup (e.g. out of range, or busy with the LabCom app).
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator)
        self._address = address

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self.coordinator, self._address)

    @property
    def available(self) -> bool:
        # Always available: show the last known value (live or restored)
        # rather than flipping to "unavailable" just because the most
        # recent poll attempt failed or hasn't happened yet this session.
        return True


class PoolLabBatterySensor(PoolLabBaseEntity, SensorEntity):
    """Battery level of the PoolLab device."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "battery"

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_battery"
        self._restored_value: int | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._restored_value = int(float(last_state.state))
            except ValueError:
                self._restored_value = None

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            value = self.coordinator.data.get("device_info", {}).get("battery_level")
            if value is not None:
                return value
        return self._restored_value


class PoolLabSignalSensor(SensorEntity):
    """Signal strength of the last advertisement, and which proxy heard it.

    Not a CoordinatorEntity: this tracks live Bluetooth reception rather than
    the result of the last on-demand read.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "signal_strength"
    _attr_icon = "mdi:signal-variant"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = True

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        self._coordinator = coordinator
        self._address = address
        self._attr_unique_id = f"{address}_signal_strength"
        self._rssi: int | None = None
        self._extra: dict[str, Any] = {}

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._coordinator, self._address)

    @property
    def native_value(self) -> int | None:
        return self._rssi

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra

    async def async_update(self) -> None:
        service_info = bluetooth.async_last_service_info(
            self.hass, self._address, connectable=True
        )
        if service_info is None:
            # Device is off/out of range; drop the value rather than keep a
            # stale one that suggests the device is still within reach.
            self._rssi = None
            self._extra = {}
            return

        self._rssi = service_info.rssi
        name = _scanner_name(self.hass, getattr(service_info, "source", None))
        self._extra = {"received_via": name or "unknown"}


class PoolLabProxySensor(SensorEntity):
    """Which Bluetooth adapter or proxy currently hears the device.

    Useful in a multi-proxy setup: reads that time out often turn out to be
    running over a weak or non-connectable route.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "via_proxy"
    _attr_icon = "mdi:access-point"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = True

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        self._coordinator = coordinator
        self._address = address
        self._attr_unique_id = f"{address}_proxy"
        self._proxy: str | None = None
        self._extra: dict[str, Any] = {}

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._coordinator, self._address)

    @property
    def native_value(self) -> str | None:
        return self._proxy

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra

    async def async_update(self) -> None:
        service_info = bluetooth.async_last_service_info(
            self.hass, self._address, connectable=True
        )
        if service_info is None:
            # Keep the last known proxy rather than blanking it: knowing where
            # the device was last heard stays useful while it is switched off.
            self._extra = {"in_range": False}
            return

        source = getattr(service_info, "source", None)
        self._proxy = _scanner_name(self.hass, source)
        self._extra = {
            "in_range": True,
            "rssi": service_info.rssi,
            "source_id": str(source) if source else None,
        }


class PoolLabStoredResultsSensor(PoolLabBaseEntity, SensorEntity):
    """Number of measurements stored on the device (max 16 cells x 16 = 256)."""

    _attr_translation_key = "stored_results"
    _attr_icon = "mdi:database"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_result_count"
        self._restored_value: int | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._restored_value = int(float(last_state.state))
            except ValueError:
                self._restored_value = None

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            value = self.coordinator.data.get("device_info", {}).get("result_count")
            if value is not None:
                return value
        return self._restored_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        value = self.native_value
        if value is None:
            return {}
        return {"maximum": DEVICE_MEMORY_SLOTS, "memory_full": value >= DEVICE_MEMORY_SLOTS}


class PoolLabClockDriftSensor(PoolLabBaseEntity, SensorEntity):
    """Difference between the device clock and Home Assistant, in seconds.

    The device timestamps every measurement itself, so drift here lands
    straight in `measured_at`. Press "Klok gelijkzetten" to correct it.
    """

    _attr_translation_key = "clock_drift"
    _attr_icon = "mdi:clock-alert-outline"
    _attr_native_unit_of_measurement = "s"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_clock_drift"

    @property
    def native_value(self) -> int | None:
        info = (self.coordinator.data or {}).get("device_info", {})
        device_time = info.get("device_time")
        read_at = info.get("read_at")
        if device_time is None or read_at is None:
            return None
        return round((device_time - read_at).total_seconds())


class PoolLabContrastSensor(PoolLabBaseEntity, SensorEntity):
    """Last known LCD contrast level (device range 18-38).

    The protocol has no "read contrast" command - the level only comes back in
    the reply to a plus/minus step, so this stays empty until you nudge it.
    """

    _attr_translation_key = "lcd_contrast"
    _attr_icon = "mdi:contrast-box"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_contrast"

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("device_info", {}).get("contrast")


class PoolLabCombinedChlorineSensor(PoolLabBaseEntity, SensorEntity):
    """Combined chlorine (chloramines), derived as total minus free.

    This is the value that tells you whether the pool needs shocking: it is the
    chlorine already spent on contaminants, and what causes the "chlorine
    smell" and stinging eyes. The device measures total chlorine in the same
    cuvette right after free chlorine, so the two are meant to be subtracted.

    Deliberately conservative about when it will produce a number - see
    `_pair()`. A difference between readings that do not belong together is
    worse than no value at all.
    """

    _attr_translation_key = "combined_chlorine"
    _attr_icon = "mdi:water-alert"
    _attr_native_unit_of_measurement = "ppm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_combined_chlorine"

    def _pair(self) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Return (free, total) only when subtracting them is meaningful."""
        measurements = (self.coordinator.data or {}).get("measurements", {})
        free = measurements.get(TYPE_FREE_CHLORINE)
        total = measurements.get(TYPE_TOTAL_CHLORINE)
        if not free or not total:
            return None
        # A clamped (overrange) reading is a lower bound, not a value; the
        # difference would be a guess presented as fact.
        if free.get("clamped") or total.get("clamped"):
            return None
        # Readings from separate sessions say nothing about each other.
        if abs(total["timestamp"] - free["timestamp"]) > COMBINED_CHLORINE_MAX_GAP_SECONDS:
            return None
        return free, total

    @property
    def native_value(self) -> float | None:
        pair = self._pair()
        if pair is None:
            return None
        free, total = pair
        # Measurement noise can make free exceed total; that means zero
        # combined chlorine, not a negative amount.
        return max(0.0, total["value"] - free["value"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pair = self._pair()
        if pair is None:
            return {"reason_unavailable": "no matching free and total chlorine reading"}

        free, total = pair
        value = max(0.0, total["value"] - free["value"])
        measured_at = _as_utc(total.get("timestamp"))
        attrs: dict[str, Any] = {
            "free_chlorine": free["value"],
            "total_chlorine": total["value"],
            "ideal_high": COMBINED_CHLORINE_IDEAL_MAX,
            "ideal_range_status": (
                IDEAL_RANGE_HIGH if value > COMBINED_CHLORINE_IDEAL_MAX else IDEAL_RANGE_OK
            ),
        }
        if measured_at is not None:
            attrs["measured_at"] = measured_at.isoformat()
        return attrs


class PoolLabLastMeasurementSensor(PoolLabBaseEntity, SensorEntity):
    """Timestamp of the most recent measurement stored on the device.

    Lets automations act on staleness ("no water test for two weeks") instead
    of only on the values themselves.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_measurement"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_last_measurement"
        self._restored_value: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._restored_value = datetime.fromisoformat(last_state.state)
            except ValueError:
                self._restored_value = None

    @property
    def native_value(self) -> datetime | None:
        measurements = (self.coordinator.data or {}).get("measurements", {})
        timestamps = [
            stamp
            for record in measurements.values()
            if (stamp := _as_utc(record.get("timestamp"))) is not None
        ]
        if timestamps:
            return max(timestamps)
        return self._restored_value


class PoolLabMeasurementSensor(PoolLabBaseEntity, SensorEntity):
    """One sensor per measurement scenario seen on the device (e.g. pH, Free Chlorine)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: PoolLabCoordinator, address: str, type_id: int
    ) -> None:
        super().__init__(coordinator, address)
        self.type_id = type_id

        name, unit, decimals = MEASUREMENT_TYPES.get(
            type_id, (f"Unknown scenario {type_id}", "ppm", 2)
        )
        self._attr_name = name
        self._attr_suggested_display_precision = decimals
        self._attr_unique_id = f"{address}_measure_{type_id}"
        self._attr_icon = "mdi:ph" if unit == "pH" else "mdi:test-tube"
        if unit == "pH":
            # SensorDeviceClass.PH only accepts `None` as its unit
            # (DEVICE_CLASS_UNITS[PH] == {None}); passing "pH" makes HA log an
            # "not a valid unit for the device class" warning per entity.
            self._attr_device_class = SensorDeviceClass.PH
            self._attr_native_unit_of_measurement = None
        else:
            self._attr_native_unit_of_measurement = unit

        self._restored_value: float | None = None
        self._restored_attrs: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._restored_value = float(last_state.state)
            except ValueError:
                self._restored_value = None
            self._restored_attrs = {
                key: last_state.attributes[key]
                for key in (
                    "status",
                    "measure_id",
                    "measured_at",
                    "ideal_low",
                    "ideal_high",
                    "ideal_range_status",
                )
                if key in last_state.attributes
            }

    @property
    def _record(self) -> dict[str, Any] | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("measurements", {}).get(self.type_id)

    @property
    def _skipped_record(self) -> dict[str, Any] | None:
        """Most recent underrange reading, which is not used as the value."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("skipped", {}).get(self.type_id)

    @property
    def native_value(self) -> float | None:
        record = self._record
        if record:
            return record["value"]
        return self._restored_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        record = self._record
        if not record:
            attrs = dict(self._restored_attrs)
            attrs.update(self._skipped_attrs())
            return attrs

        attrs: dict[str, Any] = {
            "status": MEASURE_STATUS_NAMES.get(record["status"], "unknown"),
            "measure_id": record["measure_id"],
        }

        if record.get("clamped"):
            # The device reports 0.0 on overrange; the shown value is the top of
            # the measuring range, so the real value is at least that.
            attrs["value_is_minimum"] = True



        # When the measurement was actually taken on the device. Without this
        # there is no way to tell a reading from an hour ago from one taken
        # three weeks ago, since the device is only read on demand.
        measured_at = _as_utc(record.get("timestamp"))
        if measured_at is not None:
            attrs["measured_at"] = measured_at.isoformat()

        device_range = MEASUREMENT_RANGES.get(self.type_id)
        if device_range is not None:
            attrs["range_min"], attrs["range_max"] = device_range

        ideal_range = self.coordinator.ideal_ranges.get(self.type_id)
        if ideal_range is not None:
            ideal_low, ideal_high = ideal_range
            attrs["ideal_low"] = ideal_low
            attrs["ideal_high"] = ideal_high
            value = record["value"]
            if value < ideal_low:
                attrs["ideal_range_status"] = IDEAL_RANGE_LOW
            elif value > ideal_high:
                attrs["ideal_range_status"] = IDEAL_RANGE_HIGH
            else:
                attrs["ideal_range_status"] = IDEAL_RANGE_OK

        attrs.update(self._skipped_attrs(newer_than=record["timestamp"]))
        return attrs

    def _skipped_attrs(self, newer_than: int = 0) -> dict[str, Any]:
        """Flag an underrange reading that was deliberately not used as value."""
        skipped = self._skipped_record
        if not skipped or skipped["timestamp"] <= newer_than:
            return {}
        when = _as_utc(skipped.get("timestamp"))
        return {
            "skipped_reading": MEASURE_STATUS_NAMES.get(
                skipped["status"], "unusable"
            ),
            "skipped_reading_at": when.isoformat() if when else None,
        }
