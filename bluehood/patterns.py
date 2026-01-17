"""Traffic pattern analysis for bluehood."""

from dataclasses import dataclass
from typing import Optional

from . import db


@dataclass
class Pattern:
    """Analyzed traffic pattern for a device."""
    time_description: str  # e.g., "Evenings (5PM-11PM)"
    day_description: str   # e.g., "Weekdays"
    frequency: str         # e.g., "Daily", "Occasional", "Rare"
    summary: str           # Combined human-readable summary


# Time period definitions (hour ranges)
TIME_PERIODS = {
    "early_morning": (5, 8),    # 5AM - 8AM
    "morning": (8, 12),          # 8AM - 12PM
    "afternoon": (12, 17),       # 12PM - 5PM
    "evening": (17, 21),         # 5PM - 9PM
    "night": (21, 24),           # 9PM - 12AM
    "late_night": (0, 5),        # 12AM - 5AM
}

TIME_PERIOD_NAMES = {
    "early_morning": "Early morning (5AM-8AM)",
    "morning": "Morning (8AM-12PM)",
    "afternoon": "Afternoon (12PM-5PM)",
    "evening": "Evening (5PM-9PM)",
    "night": "Night (9PM-12AM)",
    "late_night": "Late night (12AM-5AM)",
}

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _get_period_for_hour(hour: int) -> str:
    """Get the time period name for a given hour."""
    for period, (start, end) in TIME_PERIODS.items():
        if period == "late_night":
            if 0 <= hour < 5:
                return period
        elif start <= hour < end:
            return period
    return "unknown"


def _find_dominant_periods(hourly: dict[int, int], threshold: float = 0.6) -> list[str]:
    """Find time periods that account for the majority of sightings."""
    if not hourly:
        return []

    total = sum(hourly.values())
    if total == 0:
        return []

    # Aggregate by period
    period_counts: dict[str, int] = {}
    for hour, count in hourly.items():
        period = _get_period_for_hour(hour)
        period_counts[period] = period_counts.get(period, 0) + count

    # Find periods that together account for threshold of activity
    sorted_periods = sorted(period_counts.items(), key=lambda x: x[1], reverse=True)
    dominant = []
    accumulated = 0

    for period, count in sorted_periods:
        dominant.append(period)
        accumulated += count
        if accumulated / total >= threshold:
            break

    return dominant


def _format_hour_range(hours: list[int]) -> str:
    """Format a list of hours as a range string."""
    if not hours:
        return "Unknown"

    hours = sorted(hours)
    min_h = hours[0]
    max_h = hours[-1]

    def fmt(h: int) -> str:
        if h == 0:
            return "12AM"
        elif h < 12:
            return f"{h}AM"
        elif h == 12:
            return "12PM"
        else:
            return f"{h-12}PM"

    return f"{fmt(min_h)}-{fmt((max_h + 1) % 24)}"


def _analyze_time_pattern(hourly: dict[int, int]) -> str:
    """Analyze hourly distribution and return a description."""
    if not hourly:
        return "No data"

    total = sum(hourly.values())
    if total < 5:
        return "Insufficient data"

    # Find dominant periods
    dominant = _find_dominant_periods(hourly)

    if len(dominant) >= 4:
        return "All day"

    # Get the actual hour range with significant activity
    active_hours = [h for h, c in hourly.items() if c >= total * 0.05]  # 5% threshold
    if active_hours:
        hour_range = _format_hour_range(active_hours)
        period_names = [TIME_PERIOD_NAMES.get(p, p) for p in dominant[:2]]
        if len(period_names) == 1:
            return period_names[0]
        return f"{hour_range}"

    return "Sporadic"


def _analyze_day_pattern(daily: dict[int, int]) -> str:
    """Analyze daily distribution and return a description."""
    if not daily:
        return "No data"

    total = sum(daily.values())
    if total < 5:
        return "Insufficient data"

    # Check if mostly weekdays (Mon-Fri = 0-4) or weekends (Sat-Sun = 5-6)
    weekday_count = sum(daily.get(d, 0) for d in range(5))
    weekend_count = sum(daily.get(d, 0) for d in range(5, 7))

    weekday_ratio = weekday_count / total if total > 0 else 0
    weekend_ratio = weekend_count / total if total > 0 else 0

    if weekday_ratio > 0.85:
        return "Weekdays only"
    elif weekend_ratio > 0.7:
        return "Weekends only"
    elif weekday_ratio > 0.7:
        return "Mostly weekdays"
    elif weekend_ratio > 0.5:
        return "Mostly weekends"
    else:
        # Find specific days with high activity
        avg = total / 7
        active_days = [DAY_NAMES[d] for d, c in daily.items() if c > avg * 1.5]
        if active_days:
            return ", ".join(active_days)
        return "All week"


def _analyze_frequency(total_sightings: int, days_tracked: int = 30) -> str:
    """Determine visit frequency based on sighting count."""
    if total_sightings == 0:
        return "Never seen"

    avg_per_day = total_sightings / days_tracked

    if avg_per_day >= 5:
        return "Constant"
    elif avg_per_day >= 2:
        return "Very frequent"
    elif avg_per_day >= 1:
        return "Daily"
    elif avg_per_day >= 0.5:
        return "Regular"
    elif avg_per_day >= 0.15:
        return "Occasional"
    else:
        return "Rare"


async def analyze_device_pattern(mac: str, days: int = 30) -> Pattern:
    """Analyze traffic pattern for a device."""
    hourly = await db.get_hourly_distribution(mac, days)
    daily = await db.get_daily_distribution(mac, days)
    sightings = await db.get_sightings(mac, days)

    time_desc = _analyze_time_pattern(hourly)
    day_desc = _analyze_day_pattern(daily)
    frequency = _analyze_frequency(len(sightings), days)

    # Build summary
    parts = []
    if frequency not in ("Never seen", "Rare"):
        parts.append(frequency)
    if time_desc not in ("No data", "Insufficient data", "All day"):
        parts.append(time_desc.lower())
    if day_desc not in ("No data", "Insufficient data", "All week"):
        parts.append(day_desc.lower())

    if parts:
        summary = ", ".join(parts)
        summary = summary[0].upper() + summary[1:]
    else:
        summary = frequency

    return Pattern(
        time_description=time_desc,
        day_description=day_desc,
        frequency=frequency,
        summary=summary,
    )


def generate_hourly_heatmap(hourly: dict[int, int], width: int = 24) -> str:
    """Generate an ASCII heatmap of hourly activity."""
    if not hourly:
        return "No data"

    max_count = max(hourly.values()) if hourly else 1
    blocks = " ░▒▓█"

    result = []
    for hour in range(24):
        count = hourly.get(hour, 0)
        intensity = int((count / max_count) * (len(blocks) - 1)) if max_count > 0 else 0
        result.append(blocks[intensity])

    return "".join(result)


def generate_daily_heatmap(daily: dict[int, int]) -> str:
    """Generate an ASCII heatmap of daily activity."""
    if not daily:
        return "No data"

    max_count = max(daily.values()) if daily else 1
    blocks = " ░▒▓█"

    result = []
    for day in range(7):
        count = daily.get(day, 0)
        intensity = int((count / max_count) * (len(blocks) - 1)) if max_count > 0 else 0
        result.append(blocks[intensity])

    return "".join(result)
