# Copyright 2014 Ricardo Garcia Silva
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Custom exception classes for oseoserver
"""

from oseoserver.models import Order

class OseoServerError(Exception):
    pass

class ServerError(OseoServerError):
    """
    Used for errors which are related to server-side operations
    """

    pass


class UnAuthorizedOrder(OseoServerError):
    pass


class NonSoapRequestError(OseoServerError):
    pass


class InvalidPackagingError(OseoServerError):

    def __init__(self, packaging):
        self.packaging = packaging

    def __str__(self):
        return "Packaging format {} is not supported".format(self.packaging)


class InvalidOptionError(OseoServerError):

    def __init__(self, option, order_config):
        self.option = option
        self.order_config = order_config

    def __str__(self):
        order_type = self.order_config.__class__.__name__.lower()
        collection = self.order_config.collection.name
        return "{} of collection {} does not support option {}".format(
            order_type, collection, self.option)


class InvalidGlobalOptionError(InvalidOptionError):

    pass


class InvalidOptionValueError(OseoServerError):

    def __init__(self, option, value, order_config):
        self.option = option
        self.value = value
        self.order_config = order_config

    def __str__(self):
        return "Value {} is not supported for option {}".format(self.value,
                                                                self.option)

class InvalidGlobalOptionValueError(InvalidOptionValueError):

    pass


class CustomOptionParsingError(OseoServerError):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return "CustomOptionParsingError: {} {}".format(self.args, self.kwargs)


class InvalidOrderDeliveryMethodError(OseoServerError):
    pass


class OnlineDataAccessInvalidProtocol(OseoServerError):
    pass


class OnlineDataDeliveryInvalidProtocol(OseoServerError):
    pass


class OperationNotImplementedError(OseoServerError):
    pass


class SubmitWithQuotationError(OseoServerError):
    pass


class OseoError(OseoServerError):

    def __init__(self, code, text, locator=None):
        self.code = code
        self.text = text
        self.locator = locator


class InvalidOrderTypeError(OseoError):

    def __init__(self, order_type):
        locator = "orderType"
        if order_type in (Order.PRODUCT_ORDER, Order.MASSIVE_ORDER):
            code = "ProductOrderingNotSupported"
            text = "Ordering not supported"
        elif order_type == Order.SUBSCRIPTION_ORDER:
            code = "SubscriptionNotSupported"
            text = "Subscription not supported"
        elif order_type == Order.TASKING_ORDER:
            code = "FutureProductNotSupported"
            text = "Programming not supported"
        else:
            code = "InvalidParameterValue"
            text = "Invalid value for Parameter"
        super(InvalidOrderTypeError, self).__init__(code, text, locator)


class InvalidCollectionError(OseoError):

    def __init__(self):
        locator = "collectionId"
        code = "InvalidParameterValue"
        text = "Invalid value for Parameter"
        super(InvalidCollectionError, self).__init__(code, text, locator)


class InvalidDeliveryOptionError(OseoError):

    def __init__(self):
        locator = "deliveryOptions"
        code = "InvalidParameterValue"
        text = "Invalid value for Parameter"
        super(InvalidDeliveryOptionError, self).__init__(code, text, locator)


class InvalidSettingsError(OseoServerError):
    pass

