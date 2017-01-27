from django.utils.encoding import python_2_unicode_compatible
from django.db import models

from . import constants


@python_2_unicode_compatible
class OrderPendingModerationManager(models.Manager):

    def get_queryset(self):
        return super(OrderPendingModerationManager,
                     self).get_queryset().filter(
            status=constants.OrderStatus.SUBMITTED.value)


class OrderManager(models.Manager):

    def create_order(self):
        pass


class ProductOrderBatchManager(models.Manager):

    def create_batch(self):
        pass


#class OrderItemManager(models.Manager):
#
#    def create_order_item(self, batch, status, additional_status_info,
#                          order_item_specification):
#        item = self.create(
#            batch=batch,
#            status=status,
#            additional_status_info=additional_status_info,
#            remark=order_item_specification["order_item_remark"],
#            collection=order_item_specification["collection"],
#            identifier=order_item_specification.get("identifier", ""),
#            item_id=order_item_specification["item_id"]
#        )
#        item.save()
#        for name, value in order_item_specification["option"].items():
#            # assuming that the option has already been validated
#            selected_option_manager = SelectedOptionManager()
#            selected_option = selected_option_manager.create_selected_option(
#                name=name,
#                value=value,
#                customizable_item=item
#            )
#            selected_option.save()
#        for name, value in order_item_spec["scene_selection"].items():
#            item.selected_scene_selection_options.add(
#                SelectedSceneSelectionOption(option=name, value=value))
#        delivery = order_item_spec["delivery_options"]
#        if delivery is not None:
#            copies = 1 if delivery["copies"] is None else delivery["copies"]
#            sdo = SelectedDeliveryOption(
#                customizable_item=item,
#
#                delivery_type=None,
#                delivery_details=None,
#
#                annotation=delivery["annotation"],
#                copies=copies,
#                special_instructions=delivery["special_instructions"],
#                option=delivery["type"]
#            )
#            sdo.save()
#        if order_item_spec["payment"] is not None:
#            item.selected_payment_option = SelectedPaymentOption(
#                option=order_item_spec["payment"])
#        item.save()
#        return item


class SelectedOptionManager(models.Manager):

    def create_selected_option(self, name, value, customizable_item):
        selected_option = self.create(
            option=name,
            value=value,
            customizable_item=customizable_item
        )
        selected_option.save()
