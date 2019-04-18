"""
Naming conventions
classes - CamelCase
functions - lower_case_with_underscores
variables - lower_case_with_underscores
constants - UPPER_CASE_WITH_UNDERSCORES
"""
from enum import Enum


class MopsEvent:
    """Simple event class with time when event should occur and event type."""
    def __init__(self, time, event_type, packet_idx):
        self.time = time
        self.type = event_type
        self.packet_idx = packet_idx

    def __lt__(self, other):
        return self.time < other.time

class MopsEventType(Enum):
    ARRIVAL = 1
    START_SERVICE = 2
    END_SERVICE = 3