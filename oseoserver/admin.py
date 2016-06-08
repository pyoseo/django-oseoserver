from __future__ import absolute_import

from django.contrib import admin
from django.core.urlresolvers import reverse
from django.utils.html import format_html

from . import models
from .server import OseoServer


class OseoFileInline(admin.StackedInline):
    model = models.OseoFile
    extra = 1

    def has_add_permission(self, request):
        return False


class SelectedOptionInline(admin.StackedInline):
    model = models.SelectedOption
    extra = 1


class ExtensionInline(admin.StackedInline):
    model = models.Extension
    extra = 1


class SelectedDeliveryOptionInline(admin.StackedInline):
    model = models.SelectedDeliveryOption
    extra = 1


class SelectedPaymentOptionInline(admin.StackedInline):
    model = models.SelectedPaymentOption
    extra = 1


class SelectedSceneSelectionOptionInline(admin.StackedInline):
    model = models.SelectedSceneSelectionOption
    extra = 1


@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = (ExtensionInline, SelectedDeliveryOptionInline,)
    fieldsets = (
        (None, {
            'fields': ('order_type', 'status', 'status_notification',
                       'status_changed_on', 'completed_on', 'user',
                       'reference', 'priority', 'packaging',)
        }),
        ('Further info', {
            'classes': ('collapse',),
            'fields': ('remark', 'additional_status_info',
                       'mission_specific_status_info')
        }),
    )
    list_display = ('id', 'order_type', 'status', 'status_changed_on', 'user',
                    'show_batches',)
    list_filter = ('status', 'user',)
    readonly_fields = ('status_changed_on', 'completed_on',
                       'last_describe_result_access_request',)
    date_hierarchy = 'created_on'


@admin.register(models.OrderPendingModeration)
class PendingOrderAdmin(admin.ModelAdmin):
    actions = ['approve_order', 'reject_order']
    list_display = ("id", "order_type", "user")

    def get_actions(self, request):
        actions = super(PendingOrderAdmin, self).get_actions(request)
        del actions['delete_selected']
        if not request.user.is_staff:
            if 'approve_order' in actions:
                del actions['approve_order']
            if 'reject_order' in actions:
                del actions['reject_order']
        return actions

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def approve_order(self, request, queryset):
        server = OseoServer()
        for order in queryset:
            server.moderate_order(order, True)
    approve_order.short_description = "Approve selected orders"

    def reject_order(self, request, queryset):
        server = OseoServer()
        for order in queryset:
            server.moderate_order(order, False)
    reject_order.short_description = "Reject selected orders"


@admin.register(models.ProductOrder)
class ProductOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "user",)


@admin.register(models.SubscriptionOrder)
class SubscriptionOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "user",)


@admin.register(models.OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    inlines = (SelectedOptionInline, SelectedDeliveryOptionInline,
               SelectedPaymentOptionInline,
               SelectedSceneSelectionOptionInline,
               OseoFileInline,)
    fieldsets = (
        (None, {
            'fields': ('item_id', 'batch', 'status',
                       'status_changed_on', 'completed_on',
                       'identifier', 'collection',)
        }),
        ('Further info', {
            'classes': ('collapse',),
            'fields': ('remark',
                       'additional_status_info',
                       'mission_specific_status_info')
        }),
    )
    list_display = ('id', 'item_id', 'link_to_batch', 'link_to_order',
                    'identifier', 'status', 'status_changed_on',
                    'additional_status_info',)
    list_filter = ('batch__order', 'status',)
    search_fields = ("batch__order__id", "item_id", "identifier",)
    date_hierarchy = 'status_changed_on'
    readonly_fields = ('status_changed_on', 'completed_on',)

    def link_to_batch(self, obj):
        url = reverse('admin:oseoserver_batch_change', args=(obj.batch_id,))
        html = '<a href="{0}">{1}</a>'.format(url, obj.batch_id)
        return format_html(html)
    link_to_batch.short_description = 'Batch'
    link_to_batch.allow_tags = True

    def link_to_order(self, obj):
        url = reverse('admin:oseoserver_order_change',
                      args=(obj.batch.order_id,))
        html = '<a href="{0}">{1}</a>'.format(url, obj.batch.order_id)
        return format_html(html)
    link_to_order.short_description = 'Order'
    link_to_order.allow_tags = True


@admin.register(models.Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'status', 'price', 'created_on',
                    'completed_on', 'updated_on',)


@admin.register(models.SubscriptionBatch)
class SubscriptionBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'timeslot', 'collection', 'status', 'price',
                    'created_on', 'completed_on', 'updated_on',)


admin.site.register(models.DeliveryInformation)
admin.site.register(models.OnlineAddress)
admin.site.register(models.InvoiceAddress)
