# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0042_auto_20150421_1145'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriptionorder',
            name='begin_on',
            field=models.DateTimeField(default=datetime.datetime(2015, 1, 1, 0, 0), help_text=b'Date and time for when the subscription should become active.'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='subscriptionorder',
            name='end_on',
            field=models.DateTimeField(default=datetime.datetime(2025, 1, 1, 0, 0), help_text=b'Date and time for when the subscription should terminate.'),
            preserve_default=False,
        ),
    ]
