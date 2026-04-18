from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN: str = "westfalenwind"
API_URL: str = "https://www.westfalenwind.de/?type=1772708565"
DYNAMIC_API_URL: str = "https://www.westfalenwind.de/?type=1772708560"
SCAN_INTERVAL: timedelta = timedelta(minutes=15)
CONF_FETCH_TIME: str = "fetch_time"
CONF_UPDATES_PER_DAY: str = "updates_per_day"
DEFAULT_FETCH_TIME: str = "00:01"
DEFAULT_UPDATES_PER_DAY: int = 24
SUPPORTED_UPDATES_PER_DAY: list[int] = [
    1,
    2,
    4,
    6,
    12,
    24,
]
PLATFORMS: list[Platform] = [Platform.SENSOR]
