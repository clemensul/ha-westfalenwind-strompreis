from __future__ import annotations

from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import (
    CONF_FETCH_TIME,
    CONF_UPDATES_PER_DAY,
    DEFAULT_FETCH_TIME,
    DEFAULT_UPDATES_PER_DAY,
    DOMAIN,
    SUPPORTED_UPDATES_PER_DAY,
)


def _is_valid_fetch_time(value: str) -> bool:
    """Prueft, ob eine Uhrzeit im Format HH:MM gueltig ist."""
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        return False
    return True


def _coerce_updates_per_day(value: Any) -> int | None:
    """Wandelt updates_per_day robust in einen unterstuetzten Integer um."""
    try:
        updates = int(value)
    except (TypeError, ValueError):
        return None

    if updates not in SUPPORTED_UPDATES_PER_DAY:
        return None

    return updates


def _build_options_schema(data: dict[str, Any]) -> vol.Schema:
    """Erstellt das Formularschema fuer die konfigurierbaren Optionen."""
    updates_default = _coerce_updates_per_day(
        data.get(CONF_UPDATES_PER_DAY, DEFAULT_UPDATES_PER_DAY)
    )
    if updates_default is None:
        updates_default = DEFAULT_UPDATES_PER_DAY

    return vol.Schema(
        {
            vol.Required(
                CONF_FETCH_TIME,
                default=data.get(CONF_FETCH_TIME, DEFAULT_FETCH_TIME),
            ): str,
            vol.Required(
                CONF_UPDATES_PER_DAY,
                default=str(updates_default),
            ): vol.In([str(value) for value in SUPPORTED_UPDATES_PER_DAY]),
        }
    )


class WestfalenwindConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow fuer die Westfalenwind-Integration."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "WestfalenwindOptionsFlow":
        """Liefert den Options Flow fuer bestehende Eintraege."""
        return WestfalenwindOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Erstellt den Entry mit konfigurierbarem Abrufplan."""
        await self.async_set_unique_id(DOMAIN, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            fetch_time = str(user_input.get(CONF_FETCH_TIME, "")).strip()
            if not _is_valid_fetch_time(fetch_time):
                errors["base"] = "invalid_time_format"
            else:
                user_input[CONF_FETCH_TIME] = fetch_time

            updates_per_day = _coerce_updates_per_day(
                user_input.get(CONF_UPDATES_PER_DAY)
            )
            if updates_per_day is None:
                errors["base"] = "invalid_updates_per_day"
            else:
                user_input[CONF_UPDATES_PER_DAY] = updates_per_day

        if user_input is not None and not errors:
            return self.async_create_entry(
                title="Westfalenwind Strompreis",
                data={},
                options=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_options_schema(user_input or {}),
            errors=errors,
        )


class WestfalenwindOptionsFlow(config_entries.OptionsFlow):
    """Options Flow fuer nachtraegliche Anpassungen."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Zeigt und speichert Optionen fuer den Abrufplan."""
        errors: dict[str, str] = {}

        if user_input is not None:
            fetch_time = str(user_input.get(CONF_FETCH_TIME, "")).strip()
            if not _is_valid_fetch_time(fetch_time):
                errors["base"] = "invalid_time_format"
            else:
                user_input[CONF_FETCH_TIME] = fetch_time

            updates_per_day = _coerce_updates_per_day(
                user_input.get(CONF_UPDATES_PER_DAY)
            )
            if updates_per_day is None:
                errors["base"] = "invalid_updates_per_day"
            else:
                user_input[CONF_UPDATES_PER_DAY] = updates_per_day

        if user_input is not None and not errors:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(
                user_input or dict(self._config_entry.options)
            ),
            errors=errors,
        )
