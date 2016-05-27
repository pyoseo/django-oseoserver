# Copyright 2015 Ricardo Garcia Silva
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

class OseoServerError(Exception):
    """Base calss for all oseoserver errors"""
    pass


class ServerError(OseoServerError):
    """
    Used for errors which are related to server-side operations
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return "ServerError: {} {}".format(self.args, self.kwargs)


class InvalidSoapVersionError(OseoServerError):
    pass


class OseoError(OseoServerError):
    """Base class for errors that are described in the OSEO standard."""

    def __init__(self, code, text, locator=None):
        self.code = code
        self.text = text
        self.locator = locator

    def __str__(self):
        return "{0.text}: {0.locator}".format(self)


class NoApplicableCodeError(OseoError):

    def __init__(self):
        code = "NoApplicableCode"
        text = "Code not applicable"
        super(NoApplicableCodeError, self).__init__(code, text)


class InvalidParameterValueError(OseoError):

    def __init__(self, locator, value=""):
        code = "InvalidParameterValue"
        text = "Invalid value for Parameter"
        self.value = value
        super(InvalidParameterValueError, self).__init__(code, text, locator)

    def __str__(self):
        return "{0.text}: {0.locator} {0.value}".format(self)

class AuthenticationFailedError(OseoError):

    def __init__(self):
        code = "AuthenticationFailed"
        text = "Invalid or missing identity information"
        locator = "identity_token"
        super(AuthenticationFailedError, self).__init__(code, text, locator)


class AuthorizationFailedError(OseoError):

    def __init__(self, locator=None):
        code = "AuthorizationFailed"
        text = "The client is not authorized to call the operation."
        locator = locator or "orderId"
        super(AuthorizationFailedError, self).__init__(code, text, locator)


class ProductOrderingNotSupportedError(OseoError):

    def __init__(self):
        code = "ProductOrderingNotSupported"
        text = "Ordering not supported"
        locator = "orderType"
        super(ProductOrderingNotSupportedError, self).__init__(code, text,
                                                               locator)


class SubscriptionNotSupportedError(OseoError):

    def __init__(self):
        code = "SubscriptionNotSupported"
        text = "Subscription not supported"
        locator = "orderType"
        super(SubscriptionNotSupportedError, self).__init__(code, text,
                                                            locator)


class FutureProductNotSupportedError(OseoError):

    def __init__(self):
        code = "FutureProductNotSupported"
        text = "Programming not supported"
        locator = "orderType"
        super(FutureProductNotSupportedError, self).__init__(code, text,
                                                             locator)


class InvalidOrderIdentifierError(OseoError):

    def __init__(self):
        code = "InvalidOrderIdentifier"
        text = "Invalid value for order"
        locator = "orderId"
        super(InvalidOrderIdentifierError, self).__init__(code, text, locator)


class UnsupportedCollectionError(OseoError):

    def __init__(self):
        code = "UnsupportedCollection"
        text = "Subscription not supported"
        locator = "collectionId"
        super(UnsupportedCollectionError, self).__init__(code, text, locator)


class InvalidNotificationValueError(OseoError):

    def __init__(self):
        code = "InvalidNotificationValue"
        text = "Invalid value for notification"
        locator = "ws-address"
        super(InvalidNotificationValueError, self).__init__(code, text,
                                                            locator)
