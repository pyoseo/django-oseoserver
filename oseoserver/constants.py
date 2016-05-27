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

NAMESPACES = {
    "soap": "http://www.w3.org/2003/05/soap-envelope",
    "soap1.1": "http://schemas.xmlsoap.org/soap/envelope/",
    "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-"
            "wssecurity-secext-1.0.xsd",
    "ows": "http://www.opengis.net/ows/2.0",
    "oseo": "http://www.opengis.net/oseo/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}
