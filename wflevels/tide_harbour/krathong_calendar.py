"""Dates for Loy Krathong in Bangkok, expressed as local WALL_DAY values.

2026 is confirmed by the Thai government. Later dates are forecasts, not
confirmed local event programs, and should be checked as announcements appear.
Sources and date coverage are recorded in the accompanying plan.
"""
from datetime import date

DAY_ZERO = date(2000, 1, 1)
FESTIVAL_DATES = (
    date(2026, 11, 24),
    date(2027, 11, 13),
    date(2028, 11, 1),
    date(2029, 11, 20),
)
FESTIVAL_DAYS = tuple((day - DAY_ZERO).days for day in FESTIVAL_DATES)


def festival_night(day: int, seconds: float, sun_altitude: float) -> bool:
    """Whether this local instant belongs to a listed festival night.

    Solar altitude below zero defines night. After local midnight the evening's
    date is yesterday; the noon boundary is safely within daylight in Bangkok.
    """
    if sun_altitude >= 0:
        return False
    evening_day = day - (seconds % 86400 < 43200)
    return evening_day in FESTIVAL_DAYS
