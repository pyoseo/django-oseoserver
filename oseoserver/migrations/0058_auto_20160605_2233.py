# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-06-05 22:33
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0057_auto_20160531_1204'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='processorparameter',
            name='item_processor',
        ),
        migrations.AlterField(
            model_name='orderitem',
            name='collection',
            field=models.CharField(choices=[(b'dummy_collection', b'dummy_collection')], max_length=255),
        ),
        migrations.AlterField(
            model_name='subscriptionbatch',
            name='collection',
            field=models.CharField(choices=[(b'dummy_collection', b'dummy_collection')], max_length=255),
        ),
        migrations.DeleteModel(
            name='ItemProcessor',
        ),
        migrations.DeleteModel(
            name='ProcessorParameter',
        ),
    ]
