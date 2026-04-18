from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, tzinfo
from typing import Any, Callable

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    API_URL,
    CONF_FETCH_TIME,
    CONF_UPDATES_PER_DAY,
    DEFAULT_FETCH_TIME,
    DEFAULT_UPDATES_PER_DAY,
    DOMAIN,
    DYNAMIC_API_URL,
)

_LOGGER = logging.getLogger(__name__)


def _parse_api_datetime_to_utc(value: str, local_tz: tzinfo) -> datetime | None:
    """Parst API-Zeitstempel robust und liefert UTC.

    Die API liefert fuer den Tagesabruf 24h-Daten in lokaler Zeit.
    Naive Zeitstempel werden daher als Home-Assistant-Lokalzeit interpretiert,
    wodurch Sommer-/Winterzeit korrekt beruecksichtigt wird.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz)

    return parsed.astimezone(timezone.utc)


def _compress_forecast_entries(
    entries: list[dict[str, Any]],
    now_utc: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Fuehrt benachbarte Intervalle mit identischem Preis zusammen."""
    compressed: list[dict[str, Any]] = []
    current_entry: dict[str, Any] | None = None

    for entry in sorted(entries, key=lambda item: str(item.get("start", ""))):
        start = entry.get("start")
        end = entry.get("end")
        price = entry.get("price_ct_kwh")
        tariff = entry.get("tariff_name")

        if not isinstance(start, str) or not isinstance(end, str):
            continue

        if compressed:
            previous = compressed[-1]
            if (
                previous.get("end") == start
                and previous.get("price_ct_kwh") == price
                and previous.get("tariff_name") == tariff
            ):
                previous["end"] = end
                start_dt = datetime.fromisoformat(start)
                end_dt = datetime.fromisoformat(end)
                if start_dt <= now_utc < end_dt:
                    current_entry = previous
                continue

        merged_entry = {
            "start": start,
            "end": end,
            "price_ct_kwh": price,
            "tariff_name": tariff,
        }
        compressed.append(merged_entry)

        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        if start_dt <= now_utc < end_dt:
            current_entry = merged_entry

    return compressed, current_entry


class WestfalenwindCoordinator(DataUpdateCoordinator[float | None]):
    """Liest Standard-Preisdaten und bestimmt den aktuell gueltigen Preis."""

    def __init__(self, hass: HomeAssistant, options: dict[str, Any]) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self._session: aiohttp.ClientSession = async_get_clientsession(hass)
        self._options = options
        self._unsub_refresh_callbacks: list[Callable[[], None]] = []

        self.current_tariff_name: str | None = None
        self.current_valid_from: str | None = None
        self.current_valid_until: str | None = None
        self.forecast: list[dict[str, Any]] = []
        self.refresh_schedule: list[str] = []

        self._setup_refresh_schedule()

    def _resolve_schedule(self) -> tuple[int, int, list[tuple[int, int]]]:
        """Liefert konfigurierten Abrufplan als HH, MM und Uhrzeiten."""
        fetch_time = self._options.get(CONF_FETCH_TIME, DEFAULT_FETCH_TIME)
        updates_per_day = self._options.get(
            CONF_UPDATES_PER_DAY,
            DEFAULT_UPDATES_PER_DAY,
        )

        try:
            fetch_time_obj = datetime.strptime(str(fetch_time), "%H:%M")
        except ValueError:
            fetch_time_obj = datetime.strptime(DEFAULT_FETCH_TIME, "%H:%M")

        try:
            updates_per_day_int = int(updates_per_day)
        except (TypeError, ValueError):
            updates_per_day_int = DEFAULT_UPDATES_PER_DAY

        updates_per_day_int = max(1, min(updates_per_day_int, 96))

        anchor_minutes = fetch_time_obj.hour * 60 + fetch_time_obj.minute
        step_minutes = 1440 / updates_per_day_int
        schedule_raw = [
            int(round((anchor_minutes + idx * step_minutes) % 1440)) % 1440
            for idx in range(updates_per_day_int)
        ]

        schedule = sorted({(minute // 60, minute % 60) for minute in schedule_raw})
        if not schedule:
            schedule = [(0, 1)]

        return fetch_time_obj.hour, fetch_time_obj.minute, schedule

    def _setup_refresh_schedule(self) -> None:
        """Plant API-Abrufe zu festen, lokalen Uhrzeiten ein."""
        for unsub in self._unsub_refresh_callbacks:
            unsub()
        self._unsub_refresh_callbacks.clear()

        _, _, schedule = self._resolve_schedule()
        self.refresh_schedule = [
            f"{hour:02d}:{minute:02d}" for hour, minute in schedule
        ]

        async def _trigger_refresh(_: datetime) -> None:
            await self.async_request_refresh()

        for hour, minute in schedule:
            self._unsub_refresh_callbacks.append(
                async_track_time_change(
                    self.hass,
                    _trigger_refresh,
                    hour=hour,
                    minute=minute,
                    second=0,
                )
            )

    async def async_shutdown(self) -> None:
        """Raeumt geplante Zeit-Callbacks auf."""
        for unsub in self._unsub_refresh_callbacks:
            unsub()
        self._unsub_refresh_callbacks.clear()

    async def _async_update_data(self) -> float | None:
        """Laedt Tagesdaten und liefert den aktuell gueltigen Preis in ct/kWh."""
        try:
            async with self._session.get(
                API_URL,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                response.raise_for_status()
                payload_raw: Any = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(
                f"Fehler beim Abruf der Westfalenwind-Daten: {err}"
            ) from err

        if not isinstance(payload_raw, dict):
            _LOGGER.warning("Unerwartetes API-Format: Antwort ist kein JSON-Objekt")
            return None

        payload: dict[str, Any] = payload_raw

        now_utc = datetime.now(timezone.utc)
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone) or timezone.utc

        # Vor jedem Durchlauf zuruecksetzen, um veraltete Attributwerte zu vermeiden.
        self.current_tariff_name = None
        self.current_valid_from = None
        self.current_valid_until = None
        self.forecast = []

        items = payload.get("data", [])
        if not isinstance(items, list):
            _LOGGER.warning("Unerwartetes API-Format: 'data' ist keine Liste")
            return None

        current_price: float | None = None

        for item in items:
            if not isinstance(item, dict):
                continue

            start_raw = item.get("start")
            end_raw = item.get("end")
            if not isinstance(start_raw, str) or not isinstance(end_raw, str):
                continue

            start_dt = _parse_api_datetime_to_utc(start_raw, local_tz)
            end_dt = _parse_api_datetime_to_utc(end_raw, local_tz)
            if start_dt is None or end_dt is None:
                continue

            price_raw = item.get("price_ct_kwh")
            try:
                price = float(price_raw) if price_raw is not None else None
            except (TypeError, ValueError):
                price = None

            tariff_name = item.get("tariff_name")
            tariff = tariff_name if isinstance(tariff_name, str) else None

            self.forecast.append(
                {
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "price_ct_kwh": price,
                    "tariff_name": tariff,
                }
            )

            if start_dt <= now_utc < end_dt:
                self.current_tariff_name = tariff
                self.current_valid_from = start_dt.isoformat()
                self.current_valid_until = end_dt.isoformat()
                current_price = price

        self.forecast, current_entry = _compress_forecast_entries(
            self.forecast,
            now_utc,
        )

        if current_entry is not None:
            self.current_tariff_name = current_entry.get("tariff_name")
            self.current_valid_from = current_entry.get("start")
            self.current_valid_until = current_entry.get("end")
            price = current_entry.get("price_ct_kwh")
            return price if isinstance(price, float) else None

        return current_price


class WestfalenwindDynamicCoordinator(DataUpdateCoordinator[float | None]):
    """Liest den voll dynamischen Strompreis."""

    def __init__(self, hass: HomeAssistant, options: dict[str, Any]) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_dynamic",
        )
        self._session: aiohttp.ClientSession = async_get_clientsession(hass)
        self._options = options
        self._unsub_refresh_callbacks: list[Callable[[], None]] = []

        self.current_tariff_name: str | None = None
        self.current_valid_from: str | None = None
        self.current_valid_until: str | None = None
        self.forecast: list[dict[str, Any]] = []
        self.refresh_schedule: list[str] = []

        self._setup_refresh_schedule()

    def _resolve_schedule(self) -> tuple[int, int, list[tuple[int, int]]]:
        """Liefert konfigurierten Abrufplan als HH, MM und Uhrzeiten."""
        fetch_time = self._options.get(CONF_FETCH_TIME, DEFAULT_FETCH_TIME)
        updates_per_day = self._options.get(
            CONF_UPDATES_PER_DAY,
            DEFAULT_UPDATES_PER_DAY,
        )

        try:
            fetch_time_obj = datetime.strptime(str(fetch_time), "%H:%M")
        except ValueError:
            fetch_time_obj = datetime.strptime(DEFAULT_FETCH_TIME, "%H:%M")

        try:
            updates_per_day_int = int(updates_per_day)
        except (TypeError, ValueError):
            updates_per_day_int = DEFAULT_UPDATES_PER_DAY

        updates_per_day_int = max(1, min(updates_per_day_int, 96))

        anchor_minutes = fetch_time_obj.hour * 60 + fetch_time_obj.minute
        step_minutes = 1440 / updates_per_day_int
        schedule_raw = [
            int(round((anchor_minutes + idx * step_minutes) % 1440)) % 1440
            for idx in range(updates_per_day_int)
        ]

        schedule = sorted({(minute // 60, minute % 60) for minute in schedule_raw})
        if not schedule:
            schedule = [(0, 1)]

        return fetch_time_obj.hour, fetch_time_obj.minute, schedule

    def _setup_refresh_schedule(self) -> None:
        """Plant API-Abrufe zu festen, lokalen Uhrzeiten ein."""
        for unsub in self._unsub_refresh_callbacks:
            unsub()
        self._unsub_refresh_callbacks.clear()

        _, _, schedule = self._resolve_schedule()
        self.refresh_schedule = [
            f"{hour:02d}:{minute:02d}" for hour, minute in schedule
        ]

        async def _trigger_refresh(_: datetime) -> None:
            await self.async_request_refresh()

        for hour, minute in schedule:
            self._unsub_refresh_callbacks.append(
                async_track_time_change(
                    self.hass,
                    _trigger_refresh,
                    hour=hour,
                    minute=minute,
                    second=0,
                )
            )

    async def async_shutdown(self) -> None:
        """Raeumt geplante Zeit-Callbacks auf."""
        for unsub in self._unsub_refresh_callbacks:
            unsub()
        self._unsub_refresh_callbacks.clear()

    async def _async_update_data(self) -> float | None:
        """Laedt Daten von der dynamischen API und liefert den Preis in ct/kWh."""
        try:
            async with self._session.get(
                DYNAMIC_API_URL,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                response.raise_for_status()
                payload: Any = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(
                f"Fehler beim Abruf der dynamischen Westfalenwind-Daten: {err}"
            ) from err

        if not isinstance(payload, dict):
            _LOGGER.warning(
                "Unerwartetes API-Format (dynamic): Antwort ist kein JSON-Objekt"
            )
            return None

        self.current_tariff_name = None
        self.current_valid_from = None
        self.current_valid_until = None
        self.forecast = []

        local_tz = dt_util.get_time_zone(self.hass.config.time_zone) or timezone.utc

        now_utc = datetime.now(timezone.utc)

        # Aktuelles API-Format: identisch zum Standard-Endpunkt (Liste in "data").
        items = payload.get("data")
        if isinstance(items, list):
            current_price: float | None = None
            for item in items:
                if not isinstance(item, dict):
                    continue

                start_raw = item.get("start")
                end_raw = item.get("end")
                if not isinstance(start_raw, str) or not isinstance(end_raw, str):
                    continue

                start_dt = _parse_api_datetime_to_utc(start_raw, local_tz)
                end_dt = _parse_api_datetime_to_utc(end_raw, local_tz)
                if start_dt is None or end_dt is None:
                    continue

                if start_dt <= now_utc < end_dt:
                    tariff_name = item.get("tariff_name")
                    self.current_tariff_name = (
                        tariff_name if isinstance(tariff_name, str) else None
                    )
                    self.current_valid_from = start_dt.isoformat()
                    self.current_valid_until = end_dt.isoformat()

                price_raw = item.get("price_ct_kwh")
                try:
                    price = float(price_raw) if price_raw is not None else None
                except (TypeError, ValueError):
                    price = None

                tariff_name = item.get("tariff_name")
                tariff = tariff_name if isinstance(tariff_name, str) else None

                self.forecast.append(
                    {
                        "start": start_dt.isoformat(),
                        "end": end_dt.isoformat(),
                        "price_ct_kwh": price,
                        "tariff_name": tariff,
                    }
                )

                if start_dt <= now_utc < end_dt:
                    self.current_tariff_name = tariff
                    self.current_valid_from = start_dt.isoformat()
                    self.current_valid_until = end_dt.isoformat()
                    current_price = price

            self.forecast, current_entry = _compress_forecast_entries(
                self.forecast,
                now_utc,
            )

            if current_entry is not None:
                self.current_tariff_name = current_entry.get("tariff_name")
                self.current_valid_from = current_entry.get("start")
                self.current_valid_until = current_entry.get("end")
                price = current_entry.get("price_ct_kwh")
                return price if isinstance(price, float) else None

            return current_price

        # Rueckwaertskompatibilitaet: frueheres Einzelobjekt-Format.
        start_raw = payload.get("start")
        end_raw = payload.get("end")
        price_raw = payload.get("price_ct_kwh")

        if isinstance(start_raw, str):
            start_dt = _parse_api_datetime_to_utc(start_raw, local_tz)
            if start_dt is not None:
                self.current_valid_from = start_dt.isoformat()

        if isinstance(end_raw, str):
            end_dt = _parse_api_datetime_to_utc(end_raw, local_tz)
            if end_dt is not None:
                self.current_valid_until = end_dt.isoformat()

        tariff_name = payload.get("tariff_name")
        self.current_tariff_name = tariff_name if isinstance(tariff_name, str) else None

        try:
            price = float(price_raw) if price_raw is not None else None
        except (TypeError, ValueError):
            price = None

        self.forecast = [
            {
                "start": self.current_valid_from,
                "end": self.current_valid_until,
                "price_ct_kwh": price,
                "tariff_name": self.current_tariff_name,
            }
        ]
        return price
