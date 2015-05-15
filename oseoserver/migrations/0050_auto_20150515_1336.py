# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0049_auto_20150515_1204'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='subscriptionorder',
            name='begin_on',
        ),
        migrations.RemoveField(
            model_name='subscriptionorder',
            name='end_on',
        ),
    ]
