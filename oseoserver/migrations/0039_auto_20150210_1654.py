# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0038_auto_20150129_1553'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderPendingModeration',
            fields=[
            ],
            options={
                'proxy': True,
                'verbose_name_plural': 'orders pending moderation',
            },
            bases=('oseoserver.order',),
        ),
        migrations.AlterField(
            model_name='ordertype',
            name='item_availability_days',
            field=models.PositiveSmallIntegerField(default=10, help_text=b'How many days will an item be available for download after it has been generated?'),
            preserve_default=True,
        ),
    ]
