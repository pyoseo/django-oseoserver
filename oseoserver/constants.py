"""Enumerations and constants for oseoserver."""

import enum


class OrderType(enum.Enum):

    PRODUCT_ORDER = "PRODUCT_ORDER"
    SUBSCRIPTION_ORDER = "SUBSCRIPTION_ORDER"
    MASSIVE_ORDER = "MASSIVE_ORDER"
    TASKING_ORDER = "TASKING_ORDER"


class OrderStatus(enum.Enum):
    SUBMITTED = "Submitted"
    ACCEPTED = "Accepted"
    IN_PRODUCTION = "InProduction"
    SUSPENDED = "Suspended"
    CANCELLED = "Cancelled"
    COMPLETEd = "Completed"
    FAILED = "Failed"
    TERMINATED = "Terminated"
    DOWNLOADED = "Downloaded"


class Priority(enum.Enum):

    STANDARD = "STANDARD"
    FAST_TRACK = "FAST_TRACK"


class StatusNotification(enum.Enum):

    NONE = 'None'
    FINAL = 'Final'
    ALL = 'All'


class Presentation(enum.Enum):

    BRIEF = "brief"
    FULL = "full"


MASSIVE_ORDER_REFERENCE = 'Massive order'
