"""Load initial data for oseoserver.

"""

from django.core.management import BaseCommand
import oseoserver.models as models

class Command(BaseCommand):
    args = ""

    help = __doc__

    _order_types = (
        "PRODUCT_ORDER",
        "MASSIVE_ORDER",
        "SUBSCRIPTION_ORDER",
        "TASKING_ORDER",
    )

    _online_data_accesses = ("http", "ftp")


    def handle(self, *args, **options):
        item_processor = self._create_item_processor()
        self._create_order_types(item_processor)
        self._create_online_data_accesses()
        group = self._create_default_oseo_group()
        self._create_default_collection(group)

    def _create_item_processor(self):
        self.stdout.write("Creating default item processor...")
        obj, created = models.ItemProcessor.objects.get_or_create()
        return obj

    def _create_order_types(self, item_processor):
        self.stdout.write("Creating default order types...")
        for t in self._order_types:
            obj, created = models.OrderType.objects.get_or_create(
                name=t, item_processor=item_processor)

    def _create_default_oseo_group(self):
        self.stdout.write("Creating default oseo user group...")
        obj, created = models.OseoGroup.objects.get_or_create(
            name="Default group",
            authentication_class="fake.auth.class"
        )
        return obj

    def _create_default_collection(self, authorized_group):
        self.stdout.write("Creating default product collection...")
        obj, created = models.Collection.objects.get_or_create(
            name="Fake collection",
            catalogue_endpoint="http://fake/csw/catalogue",
            collection_id="fake_id"
        )
        obj.authorized_groups.add(authorized_group)
        obj.save()

    def _create_online_data_accesses(self):
        self.stdout.write("Creating default online data access protocols...")
        for p in self._online_data_accesses:
            obj, created = models.OnlineDataAccess.objects.get_or_create(
                protocol=p)
