"""Unit tests for oseoserver.operations.getstatus"""

import pytest
import mock

from oseoserver.operations import getstatus
from oseoserver import constants
from oseoserver import errors

pytestmark = pytest.mark.unit


class TestGetStatus(object):

    def test_creation(self):
        getstatus.GetStatus()
