# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0050_auto_20150515_1336'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriptionorder',
            name='begin_on',
            field=models.DateTimeField(default=datetime.datetime(2015, 5, 15, 13, 45, 21, 14378, tzinfo=utc), help_text=b'Date and time for when the subscription should become active.'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='subscriptionorder',
            name='end_on',
            field=models.DateTimeField(default=datetime.datetime(2015, 5, 15, 13, 45, 36, 126368, tzinfo=utc), help_text=b'Date and time for when the subscription should terminate.'),
            preserve_default=False,
        ),
    ]
