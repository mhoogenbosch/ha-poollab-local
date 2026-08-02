"""Data update coordinator for PoolLab Local.

Implements the active-connection Command/Response protocol described in the
official PoolLab 1.0 BLE API documentation:
  1. Connect (no pairing/bonding).
  2. Discover PoolLabSvc and its three characteristics.
  3. Enable notifications on MISO_Signal.
  4. To run a command: write it to CommandMOSI, wait for a MISO_Signal
     notification (its payload is irrelevant - it's only a "ready" ping),
     then read the response from CommandMISO.
"""
from __future__ import annotations

import asyncio
import logging
import math
import struct
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHAR_MISO_CMD_UUID,
    CHAR_MISO_SIGNAL_UUID,
    CHAR_MOSI_CMD_UUID,
    CMD_GET_INFO,
    CMD_GET_MEASURES,
    CMD_GET_PPM_MGL,
    CMD_RESET_DEVICE,
    CMD_RESET_MEASURES,
    CMD_SET_CONTRAST_MINUS,
    CMD_SET_CONTRAST_PLUS,
    CMD_SET_PPM_MGL,
    CMD_SET_TIME,
    CMD_SLEEP_DEVICE,
    DEFAULT_TIMEOUT,
    IDEAL_RANGES,
    MEASURE_STATUS_OVERRANGE,
    MEASURE_STATUS_UNDERRANGE,
    MEASUREMENT_RANGES,
    MEASUREMENT_TYPES,
    PREAMBLE,
    RESULT_ERR,
    UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class PoolLabCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls a PoolLab 1.0 device over BLE and caches the latest readings."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"PoolLab ({address})",
            update_interval=(
                timedelta(seconds=UPDATE_INTERVAL_SECONDS)
                if UPDATE_INTERVAL_SECONDS
                else None
            ),
        )
        self.address = address
        # The device only accepts one central connection at a time, and a
        # full poll involves several sequential command/response round
        # trips, so we serialize polls defensively even though the
        # coordinator itself shouldn't normally overlap calls.
        self._lock = asyncio.Lock()
        # The device has no "get contrast" command, so the level is only known
        # after a plus/minus step. None until the user nudges it.
        self._contrast: int | None = None
        # Target ranges, set from the config entry (options flow layered over
        # the defaults in const.py). Not protocol data - purely presentation.
        self.ideal_ranges: dict[int, tuple[float, float]] = dict(IDEAL_RANGES)

    async def _async_update_data(self) -> dict[str, Any]:
        async with self._lock:
            return await self._poll_device()

    async def _connect(self):
        """Connect and subscribe to MISO_Signal; returns (client, response_ready)."""
        ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"PoolLab {self.address} was not seen by any Bluetooth "
                "adapter/proxy. Make sure it is powered on and in range."
            )

        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.address,
            max_attempts=3,
        )

        response_ready = asyncio.Event()

        def _on_signal_notify(_sender: Any, _data: bytearray) -> None:
            # Payload is irrelevant; this is purely a "data is ready" ping.
            response_ready.set()

        await client.start_notify(CHAR_MISO_SIGNAL_UUID, _on_signal_notify)
        return client, response_ready

    async def async_set_device_time(self) -> None:
        """Set the device clock to the current time (PCMD_API_SET_TIME).

        The device stamps each measurement with its own clock, so drift there
        shows up directly in the `measured_at` attribute.
        """
        async with self._lock:
            client: BleakClientWithServiceCache | None = None
            try:
                client, response_ready = await self._connect()
                now = int(time.time())
                await self._send_command(
                    client, response_ready, CMD_SET_TIME, struct.pack("<I", now)
                )
                _LOGGER.info(
                    "PoolLab clock set to %s",
                    datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
                )
            except TimeoutError as err:
                raise UpdateFailed(f"Timed out setting PoolLab clock: {err}") from err
            except BleakError as err:
                raise UpdateFailed(f"Bluetooth error setting PoolLab clock: {err}") from err
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except BleakError:
                        pass

        # Pull fresh data so the reported device_time reflects the new clock.
        await self.async_request_refresh()

    async def _fire_and_forget(self, command_id: int, label: str) -> None:
        """Send a command that produces no response.

        RESET_DEVICE and SLEEP_DEVICE kill the radio immediately, so there is
        no notification to wait for. Per the API docs the write itself may even
        fail depending on the platform - that is expected, not an error.
        """
        async with self._lock:
            client: BleakClientWithServiceCache | None = None
            try:
                client, _ = await self._connect()
                payload = bytearray(7)
                payload[0] = PREAMBLE
                payload[1] = command_id & 0xFF
                payload[2] = (command_id >> 8) & 0xFF
                try:
                    await client.write_gatt_char(
                        CHAR_MOSI_CMD_UUID, bytes(payload), response=False
                    )
                except (BleakError, TimeoutError) as err:
                    _LOGGER.debug(
                        "%s: write reported %s - expected, the device drops the "
                        "connection immediately", label, err
                    )
                _LOGGER.info("PoolLab: %s sent", label)
            except TimeoutError as err:
                raise UpdateFailed(f"Timed out sending {label}: {err}") from err
            except BleakError as err:
                raise UpdateFailed(f"Bluetooth error sending {label}: {err}") from err
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except BleakError:
                        pass

    async def async_sleep_device(self) -> None:
        """Put the device into deep sleep (same as holding the power button)."""
        await self._fire_and_forget(CMD_SLEEP_DEVICE, "sleep")

    async def async_reset_device(self) -> None:
        """Restart the device."""
        await self._fire_and_forget(CMD_RESET_DEVICE, "restart")

    async def async_reset_measures(self) -> None:
        """Erase every stored measurement on the device. Irreversible."""
        async with self._lock:
            client: BleakClientWithServiceCache | None = None
            try:
                client, response_ready = await self._connect()
                raw = await self._send_command(
                    client, response_ready, CMD_RESET_MEASURES, b""
                )
                if len(raw) > 1 and raw[1] == RESULT_ERR:
                    raise UpdateFailed("PoolLab refused to erase its memory")
                _LOGGER.info("PoolLab: stored measurements erased")
            except TimeoutError as err:
                raise UpdateFailed(f"Timed out erasing PoolLab memory: {err}") from err
            except BleakError as err:
                raise UpdateFailed(f"Bluetooth error erasing PoolLab memory: {err}") from err
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except BleakError:
                        pass

        await self.async_request_refresh()

    async def async_step_contrast(self, increase: bool) -> int | None:
        """Nudge the LCD contrast one level (range 18-38); returns the new level."""
        command = CMD_SET_CONTRAST_PLUS if increase else CMD_SET_CONTRAST_MINUS
        label = "contrast up" if increase else "contrast down"
        async with self._lock:
            client: BleakClientWithServiceCache | None = None
            try:
                client, response_ready = await self._connect()
                raw = await self._send_command(client, response_ready, command, b"")
                if len(raw) < 4:
                    return None
                if raw[1] == RESULT_ERR:
                    # Already at the end of the range - not a failure worth raising.
                    _LOGGER.info("PoolLab: %s refused (already at the limit)", label)
                    return None
                level = struct.unpack_from("<H", raw, 2)[0]
                _LOGGER.info("PoolLab: contrast is now %s", level)
                self._contrast = level
                return level
            except TimeoutError as err:
                raise UpdateFailed(f"Timed out setting contrast: {err}") from err
            except BleakError as err:
                raise UpdateFailed(f"Bluetooth error setting contrast: {err}") from err
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except BleakError:
                        pass

    async def async_set_unit_mode(self, mg_per_litre: bool) -> None:
        """Switch the device between ppm and mg/L display mode."""
        async with self._lock:
            client: BleakClientWithServiceCache | None = None
            try:
                client, response_ready = await self._connect()
                await self._send_command(
                    client,
                    response_ready,
                    CMD_SET_PPM_MGL,
                    bytes([1 if mg_per_litre else 0]),
                )
                _LOGGER.info(
                    "PoolLab: unit mode set to %s", "mg/L" if mg_per_litre else "ppm"
                )
            except TimeoutError as err:
                raise UpdateFailed(f"Timed out setting unit mode: {err}") from err
            except BleakError as err:
                raise UpdateFailed(f"Bluetooth error setting unit mode: {err}") from err
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except BleakError:
                        pass

        await self.async_request_refresh()

    async def _poll_device(self) -> dict[str, Any]:
        client: BleakClientWithServiceCache | None = None
        try:
            client, response_ready = await self._connect()

            info_raw = await self._send_command(
                client, response_ready, CMD_GET_INFO, b""
            )
            info = self._parse_info(info_raw)

            # Unit mode is a separate command; cheap enough to fold into the poll.
            try:
                unit_raw = await self._send_command(
                    client, response_ready, CMD_GET_PPM_MGL, b""
                )
                if len(unit_raw) > 1 and unit_raw[0] == PREAMBLE:
                    info["unit_mode"] = "mg/L" if unit_raw[1] == 1 else "ppm"
            except (TimeoutError, BleakError) as err:
                _LOGGER.debug("Could not read unit mode: %s", err)

            result_count = info["result_count"]
            measurements: dict[int, dict[str, Any]] = {}
            skipped: dict[int, dict[str, Any]] = {}

            cell_id = 0
            results_read = 0
            while results_read < result_count and cell_id < 16:
                for half in (0, 1):
                    if results_read >= result_count:
                        break
                    params = struct.pack("<HB", cell_id, half)
                    raw = await self._send_command(
                        client, response_ready, CMD_GET_MEASURES, params
                    )
                    for record in self._parse_measurements(raw):
                        if record is None:
                            continue
                        results_read += 1

                        # An underrange reading means the photometer saw no
                        # colouring at all - typically a measurement taken
                        # without a reagent tablet. Letting that 0.0 overwrite a
                        # good value would poison both the state and long-term
                        # statistics. Overrange is kept: "higher than I can
                        # measure" is real, actionable information.
                        unusable = record["status"] == MEASURE_STATUS_UNDERRANGE or (
                            record["status"] == MEASURE_STATUS_OVERRANGE
                            and not record["clamped"]
                        )
                        target = skipped if unusable else measurements
                        existing = target.get(record["type_id"])
                        if existing is None or record["timestamp"] > existing["timestamp"]:
                            target[record["type_id"]] = record
                cell_id += 1

            info["contrast"] = self._contrast

            return {
                "device_info": info,
                "measurements": measurements,
                "skipped": skipped,
            }

        except TimeoutError as err:
            raise UpdateFailed(f"Timed out talking to PoolLab: {err}") from err
        except BleakError as err:
            raise UpdateFailed(f"Bluetooth error talking to PoolLab: {err}") from err
        finally:
            if client is not None:
                try:
                    await client.disconnect()
                except BleakError:
                    pass

    @staticmethod
    async def _send_command(
        client: BleakClientWithServiceCache,
        response_ready: asyncio.Event,
        command_id: int,
        params: bytes,
    ) -> bytes:
        """Write one command, wait for the ready-notification, read the response."""
        response_ready.clear()

        payload = bytearray(max(7, 3 + len(params)))
        payload[0] = PREAMBLE
        payload[1] = command_id & 0xFF
        payload[2] = (command_id >> 8) & 0xFF
        payload[3 : 3 + len(params)] = params

        await client.write_gatt_char(
            CHAR_MOSI_CMD_UUID, bytes(payload), response=True
        )

        async with asyncio.timeout(DEFAULT_TIMEOUT):
            await response_ready.wait()

        raw = await client.read_gatt_char(CHAR_MISO_CMD_UUID)
        return bytes(raw)

    @staticmethod
    def _parse_info(raw: bytes) -> dict[str, Any]:
        """Parse the PCMD_API_GET_INFO response (dev_info_response struct)."""
        if len(raw) < 23 or raw[0] != PREAMBLE:
            raise UpdateFailed("Malformed GET_INFO response from PoolLab")

        active_id, fw_version, result_count = struct.unpack_from("<HHH", raw, 1)
        device_time_raw = int.from_bytes(raw[7:15], byteorder="little")
        mac = raw[15:21]
        battery_level = struct.unpack_from("<H", raw, 21)[0]

        # An uninitialised or corrupted device clock (the field is a uint64)
        # would otherwise raise OverflowError/OSError out of fromtimestamp and
        # abort the whole poll with an unhelpful traceback.
        device_time: datetime | None = None
        if device_time_raw:
            try:
                device_time = datetime.fromtimestamp(device_time_raw, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                _LOGGER.debug(
                    "PoolLab reported an implausible device clock (%s); ignoring",
                    device_time_raw,
                )

        return {
            # When we read the clock, so the drift can be derived later.
            "read_at": datetime.now(tz=timezone.utc),
            "active_id": active_id,
            "fw_version": fw_version,
            "result_count": result_count,
            "device_time": device_time,
            "mac_address": ":".join(f"{b:02X}" for b in mac),
            "battery_level": battery_level,
        }

    @staticmethod
    def _parse_measurements(raw: bytes) -> list[dict[str, Any] | None]:
        """Parse the 8 flash_measurement_result records in a GET_MEASURES reply."""
        if not raw or raw[0] != PREAMBLE:
            return [None] * 8

        body = raw[1:]
        records: list[dict[str, Any] | None] = []

        for i in range(8):
            chunk = body[i * 16 : i * 16 + 16]
            if len(chunk) < 16 or chunk == b"\x00" * 16:
                records.append(None)
                continue

            measure_id, measure_type, measure_status = struct.unpack_from(
                "<HBB", chunk, 0
            )
            timestamp = struct.unpack_from("<I", chunk, 4)[0]
            (value,) = struct.unpack_from("<f", chunk, 8)

            if measure_type == 0 and timestamp == 0:
                records.append(None)
                continue

            # A corrupted record can decode to NaN/inf, which would end up as a
            # literal "nan" sensor state and poison long-term statistics.
            if not math.isfinite(value):
                _LOGGER.debug(
                    "Skipping PoolLab record %s (type %s): non-finite value",
                    measure_id,
                    measure_type,
                )
                records.append(None)
                continue

            name, unit, _decimals = MEASUREMENT_TYPES.get(
                measure_type, (f"Unknown scenario {measure_type}", "ppm", 2)
            )

            # On overrange the device reports value 0.0 - the reading simply did
            # not fit its scale. Taking that at face value is actively wrong: a
            # total alkalinity above 200 ppm would show as 0.0 and be judged
            # "too low", the exact opposite of reality. Clamp to the top of the
            # measuring range instead, so the value reads as "at least this".
            clamped = False
            if measure_status == MEASURE_STATUS_OVERRANGE:
                device_range = MEASUREMENT_RANGES.get(measure_type)
                if device_range is not None:
                    value = device_range[1]
                    clamped = True

            records.append(
                {
                    "measure_id": measure_id,
                    "type_id": measure_type,
                    "name": name,
                    "unit": unit,
                    "status": measure_status,
                    "timestamp": timestamp,
                    # Store the device value as-is. Rounding here loses
                    # precision and made Home Assistant disagree with the
                    # device display (0.026 showed as 0.03 while the device
                    # shows 0.02). Presentation is handled by the entity's
                    # suggested_display_precision instead.
                    "value": value,
                    # True when the value is the top of the measuring range
                    # rather than a real reading: the actual value is at least
                    # this much.
                    "clamped": clamped,
                }
            )

        return records
