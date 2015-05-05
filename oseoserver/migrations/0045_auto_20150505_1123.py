# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0044_oseofile_last_downloaded_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orderitem',
            name='item_id',
            field=models.CharField(help_text=b'Id for the item in the order request', max_length=80),
            preserve_default=True,
        ),
    ]
