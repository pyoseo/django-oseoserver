from __future__ import absolute_import

from django.contrib import admin
from django.core.urlresolvers import reverse
from django.utils.html import format_html

from . import models
from . import requestprocessor
from . import utilities


def order_change_form_link(instance):
    change_form_url = reverse("admin:oseoserver_order_change",
                              args=(instance.id,))
    return format_html('<a href="{}">{}</a>', change_form_url, instance.id)
order_change_form_link.short_description = "Order"


def batch_order_change_form_link(instance):
    order = instance.order
    change_form_url = reverse("admin:oseoserver_order_change",
                              args=(order.id,))
    return format_html(
        '<a href="{}">{} {}</a>', change_form_url, order.order_type, order.id)
batch_order_change_form_link.short_description = "Order"


def delivery_information_change_form_link(instance):
    if instance.id is not None:
        change_form_url = reverse(
            "admin:oseoserver_deliveryinformation_change", args=(instance.id,))
        result = format_html(
            '<a href="{}">Delivery information {}</a>',
            change_form_url,
            instance.id
        )
    else:
        result = "Order does not specify any delivery information"
    return result
delivery_information_change_form_link.short_description = "Details"


def item_specification_change_form_link(instance):
    change_form_url = reverse(
        "admin:oseoserver_itemspecification_change", args=(instance.id,))
    result = format_html(
        '<a href="{}">Item specification {}</a>', change_form_url, instance.id)
    return result
item_specification_change_form_link.short_description = "Details"


def order_change_form_link(instance):
    order_id = instance.order.id
    change_form_url = reverse(
        "admin:oseoserver_order_change", args=(order_id,))
    result = format_html(
        '<a href="{}">Order {}</a>', change_form_url, order_id)
    return result
order_change_form_link.short_description = "Order"


class OrderItemInline(admin.StackedInline):
    model = models.OrderItem
    extra = 0


class OnlineAddressInline(admin.StackedInline):
    model = models.OnlineAddress
    extra = 1


class SelectedPaymentOptionInline(admin.StackedInline):
    model = models.SelectedPaymentOption
    extra = 0


class SelectedSceneSelectionOptionInline(admin.StackedInline):
    model = models.SelectedSceneSelectionOption
    extra = 0


class SelectedOrderOptionInline(admin.StackedInline):
    model = models.SelectedOrderOption
    extra = 0


class SelectedItemOptionInline(admin.StackedInline):
    model = models.SelectedItemOption
    extra = 0


class OrderDeliveryOptionInline(admin.StackedInline):
    model = models.OrderDeliveryOption
    extra = 0


class ItemSpecificationDeliveryOptionInline(admin.StackedInline):
    model = models.ItemSpecificationDeliveryOption
    extra = 1


class DeliveryInformationInline(admin.StackedInline):
    model = models.DeliveryInformation
    extra = 1
    fields = (
        "id",
        delivery_information_change_form_link,
    )
    readonly_fields = (
        delivery_information_change_form_link,
    )


class ItemSpecificationInline(admin.StackedInline):
    model = models.ItemSpecification
    extra = 0
    fields = (
        "collection",
        "identifier",
        item_specification_change_form_link,
    )
    readonly_fields = (
        item_specification_change_form_link,
    )


@admin.register(models.Batch)
class BatchAdmin(admin.ModelAdmin):
    inlines = (
        OrderItemInline,
    )
    list_display = (
        "id",
        "order",
        "status",
    )
    fields = (
        batch_order_change_form_link,
        "status",
    )
    readonly_fields = (
        batch_order_change_form_link,
        "status",
    )


@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = (
        SelectedOrderOptionInline,
        OrderDeliveryOptionInline,
        DeliveryInformationInline,
        ItemSpecificationInline,
    )
    fieldsets = (
        (None, {
            "fields": (
                "order_type",
                "status",
                "status_notification",
                "status_changed_on",
                "completed_on",
                "user",
                "reference",
                "priority",
                "packaging",
                "extensions",
                #"selected_options",
            )
        }),
        ("Further info", {
            "classes": ("collapse",),
            "fields": (
                "remark",
                "additional_status_info",
                "mission_specific_status_info",
            )
        }),
    )
    list_display = (
        "id",
        "order_type",
        "status",
        "status_changed_on",
        "user",
    )
    list_display_links = (
        "order_type",
    )
    list_filter = (
        "status",
        "user",
        "order_type",
    )
    readonly_fields = (
        "order_type",
        "status",
        "status_changed_on",
        "completed_on",
        "last_describe_result_access_request",
    )
    date_hierarchy = "created_on"


@admin.register(models.OrderPendingModeration)
class PendingOrderAdmin(admin.ModelAdmin):
    actions = ["approve_order", "reject_order"]
    list_display = (order_change_form_link, "order_type", "user")
    list_display_links = None

    def get_actions(self, request):
        actions = super(PendingOrderAdmin, self).get_actions(request)
        del actions["delete_selected"]
        if not request.user.is_staff:
            if "approve_order" in actions:
                del actions["approve_order"]
            if "reject_order" in actions:
                del actions["reject_order"]
        return actions

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def approve_order(self, request, queryset):
        moderated_order_ids = []
        for order in queryset:
            moderated_order_ids.append(order.id)
            config = utilities.get_generic_order_config(order.order_type)
            requestprocessor.handle_submit(
                order=order,
                approved=True,
                notify=config["notifications"]["moderation"]
            )
        if len(moderated_order_ids) == 1:
            msg = "Order {} has been approved".format(moderated_order_ids[0])
        else:
            msg = "Orders {} have been approved".format(
                ", ".join(str(id_) for id_ in moderated_order_ids))
        self.message_user(request, message=msg)
    approve_order.short_description = "Approve selected orders"

    def reject_order(self, request, queryset):
        moderated_order_ids = []
        for order in queryset:
            moderated_order_ids.append(order.id)
            config = utilities.get_generic_order_config(order.order_type)
            requestprocessor.handle_submit(
                order=order,
                approved=False,
                notify=config["notifications"]["moderation"]
            )
        if len(moderated_order_ids) == 1:
            msg = "Order {} has been rejected".format(moderated_order_ids[0])
        else:
            msg = "Orders {} have been rejected".format(
                ", ".join(str(id_) for id_ in moderated_order_ids))
        self.message_user(request, message=msg)
    reject_order.short_description = "Reject selected orders"


@admin.register(models.ItemSpecification)
class ItemSpecificationAdmin(admin.ModelAdmin):
    readonly_fields = (
        #"order",
        order_change_form_link,
    )
    fields = (
        # "order",
        order_change_form_link,
        "item_id",
        "collection",
        "identifier",
        "remark",
        "extension",
    )
    inlines = (
        SelectedItemOptionInline,
        ItemSpecificationDeliveryOptionInline,
    )

    def get_model_perms(self, request):
        # This is a hack to hide this model from the admin index
        # We should be using ModelAdmin.has_module_permission() instead
        # but there is a django bug that prevents it. See:
        # https://github.com/django/django/pull/7367
        # for more details. This should be fixed in django v1.11+
        return {}


@admin.register(models.OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {
            "fields": (
                "identifier",
                "url",
                "link_to_batch",
                "link_to_item_specification",
                "status",
                "available",
                "status_changed_on",
                "completed_on",
            )
        }),
        ("Further info", {
            "classes": ("collapse",),
            "fields": (
                "expires_on",
                "downloads",
                "last_downloaded_at",
                "additional_status_info",
                "mission_specific_status_info",
            )
        }),
    )
    list_display = (
        "id",
        "status",
        "available",
        "link_to_batch",
        "link_to_order",
        "identifier",
        "status_changed_on",
    )
    list_filter = (
        "status",
    )
    search_fields = (
        "batch__order__id",
        "identifier",
    )
    date_hierarchy = "status_changed_on"
    readonly_fields = (
        "identifier",
        "url",
        "status",
        "status_changed_on",
        "completed_on",
        "available",
        "link_to_batch",
        "link_to_item_specification",
        "item_specification",
        "expires_on",
        "downloads",
        "last_downloaded_at",
        "additional_status_info",
        "mission_specific_status_info",
    )

    def link_to_batch(self, obj):
        url = reverse("admin:oseoserver_batch_change", args=(obj.batch_id,))
        html = "<a href='{0}'>{1}</a>".format(url, obj.batch_id)
        return format_html(html)
    link_to_batch.short_description = "Batch"
    link_to_batch.allow_tags = True

    def link_to_order(self, obj):
        url = reverse("admin:oseoserver_order_change",
                      args=(obj.batch.order_id,))
        html = "<a href='{0}'>{1}</a>".format(url, obj.batch.order_id)
        return format_html(html)
    link_to_order.short_description = "Order"
    link_to_order.allow_tags = True

    def link_to_item_specification(self, obj):
        url = reverse("admin:oseoserver_itemspecification_change",
                      args=(obj.item_specification.id,))
        html = "<a href='{0}'>Item specification {1}</a>".format(
            url, obj.item_specification.id)
        return format_html(html)
    link_to_item_specification.short_description = "Item specification"
    link_to_item_specification.allow_tags = True


@admin.register(models.DeliveryInformation)
class DeliveryInformationAdmin(admin.ModelAdmin):
    inlines = (
        OnlineAddressInline,
    )
    fieldsets = (
        (None, {
            "fields": (
                "order",
                "first_name",
                "city",
                "country",
            )
        }),
        ("Further info", {
            "classes": ("collapse",),
            "fields": (
                "first_name",
                "city",
                "country",
            )
        }),
    )
    readonly_fields = (
        "order",
    )
