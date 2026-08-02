"""Config flow for the PoolLab Local integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import CONFIGURABLE_TARGETS, DOMAIN, IDEAL_RANGES, OPT_TARGETS, SERVICE_UUID


def _looks_like_poollab(info: BluetoothServiceInfoBleak) -> bool:
    if SERVICE_UUID.lower() in [uuid.lower() for uuid in info.service_uuids]:
        return True
    return bool(info.name and "poollab" in info.name.lower())


class PoolLabConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PoolLab Local."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_devices: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Target ranges are editable after setup."""
        return PoolLabOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a PoolLab device discovered by Home Assistant's Bluetooth integration."""
        if not _looks_like_poollab(discovery_info):
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovered_devices[discovery_info.address] = (
            discovery_info.name or "PoolLab"
        )
        self.context["title_placeholders"] = {
            "name": discovery_info.name or "PoolLab"
        }
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a single auto-discovered device."""
        address = next(iter(self._discovered_devices))

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_devices[address],
                data={CONF_ADDRESS: address},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._discovered_devices[address]},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup: let the user pick from currently visible devices."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices.get(address, "PoolLab"),
                data={CONF_ADDRESS: address},
            )

        current_addresses = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current_addresses:
                continue
            if not _looks_like_poollab(info):
                continue
            self._discovered_devices[info.address] = info.name or "PoolLab"

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )


class PoolLabOptionsFlow(OptionsFlow):
    """Lets the user set their own target ranges from the UI.

    These used to live in const.py, which meant every edit was wiped by the
    next update. Stored in the config entry instead, so they survive.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the target ranges."""
        errors: dict[str, str] = {}
        stored: dict[str, list[float]] = self.config_entry.options.get(OPT_TARGETS, {})

        if user_input is not None:
            targets: dict[str, list[float]] = {}
            for key in CONFIGURABLE_TARGETS:
                low = user_input.get(f"{key}_min")
                high = user_input.get(f"{key}_max")
                if low is None or high is None:
                    continue
                if low >= high:
                    errors[f"{key}_min"] = "min_not_below_max"
                    continue
                targets[key] = [low, high]

            if not errors:
                return self.async_create_entry(data={OPT_TARGETS: targets})

        def _current(key: str, index: int) -> float:
            if key in stored:
                return stored[key][index]
            return IDEAL_RANGES[CONFIGURABLE_TARGETS[key]][index]

        schema: dict[Any, Any] = {}
        for key in CONFIGURABLE_TARGETS:
            schema[vol.Required(f"{key}_min", default=_current(key, 0))] = vol.Coerce(float)
            schema[vol.Required(f"{key}_max", default=_current(key, 1))] = vol.Coerce(float)

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
