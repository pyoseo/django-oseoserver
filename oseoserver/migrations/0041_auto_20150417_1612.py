# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0040_subscriptionbatch'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='subscriptionbatch',
            options={'verbose_name_plural': 'subscription batches'},
        ),
        migrations.RemoveField(
            model_name='derivedorder',
            name='collections',
        ),
    ]
