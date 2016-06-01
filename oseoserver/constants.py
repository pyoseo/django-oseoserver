"""Enumerations and constants for oseoserver."""

import enum

ENCODING = "utf-8"

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
    COMPLETED = "Completed"
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


class DeliveryOption(enum.Enum):

    MEDIA_DELIVERY = "mediadelivery"
    ONLINE_DATA_ACCESS = "onlinedataaccess"
    ONLINE_DATA_DELIVERY = "onlinedatadelivery"


class DeliveryOptionProtocol(enum.Enum):

    FTP = "ftp"
    SFTP = "sftp"
    FTPS = "ftps"
    P2P = "P2P"
    WCS = "wcs"
    WMS = "wms"
    E_MAIL = "e-mail"
    DDS = "dds"
    HTTP = "http"
    HTTPS = "https"


class DeliveryMedium(enum.Enum):

    NTP = "NTP"
    DAT = "DAT"
    EXABYTE = "Exabyte"
    CD_ROM = "CD-ROM"
    DLT = "DLT"
    D1 = "D1"
    DVD = "DVD"
    BD = "BD"
    LTO = "LTO"
    LTO2 = "LTO2"
    LTO4 = "LTO4"


class DeliveryMethod(enum.Enum):

    EACH_READY = "as each product is reasy"
    ALL_READY = "once all products are ready"
    OTHER = "other"


class Packaging(enum.Enum):

    ZIP = "zip"


