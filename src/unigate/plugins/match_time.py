"""Time matcher plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class DayOfWeekMatcher:
    """Match by day of week."""
    
    name = "day_of_week"
    type = "match"
    
    DAYS = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        current_day = msg.ts.weekday()
        days = [self.DAYS[d.lower()] for d in (value if isinstance(value, list) else [value])]
        return current_day in days


class HourOfDayMatcher:
    """Match by hour of day."""
    
    name = "hour_of_day"
    type = "match"
    
    def match(self, msg: Message, value: int | list[int] | str) -> bool:
        current_hour = msg.ts.hour
        
        if isinstance(value, str) and "-" in value:
            start, end = map(int, value.split("-"))
            return start <= current_hour <= end
        elif isinstance(value, list):
            return current_hour in value
        else:
            return current_hour == value


class TimeRangeMatcher:
    """Match by time range (HH:MM-HH:MM)."""
    
    name = "time_range"
    type = "match"
    
    def match(self, msg: Message, value: str) -> bool:
        from datetime import time
        
        try:
            start_str, end_str = value.split("-")
            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))
            
            msg_time = msg.ts.time()
            start = time(start_hour, start_min)
            end = time(end_hour, end_min)
            
            if start <= end:
                return start <= msg_time <= end
            else:
                return msg_time >= start or msg_time <= end
        except (ValueError, AttributeError):
            return False
