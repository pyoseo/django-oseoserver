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
Custom django signals for oseoserver
"""

from django.dispatch import Signal

# TODO - Implement signals for the following:
#order_request_received
#order_waiting_moderation
#subscription_accepted
#subscription_terminated
#batch_completed
#order_item_completed
#order_completed
#order_item_failed
#batch_failed
#order_failed

order_status_changed = Signal(
    providing_args=["instance", "old_status", "new_status"])

order_submitted = Signal(providing_args=["instance"])
order_accepted = Signal(providing_args=["instance"])
order_in_production = Signal(providing_args=["instance"])
order_failed = Signal(providing_args=["instance"])
order_completed = Signal(providing_args=["instance"])
order_downloaded = Signal(providing_args=["instance"])
order_cancelled = Signal(providing_args=["instance"])
order_terminated = Signal(providing_args=["instance"])
