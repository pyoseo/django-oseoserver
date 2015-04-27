# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0043_auto_20150424_1416'),
    ]

    operations = [
        migrations.AddField(
            model_name='oseofile',
            name='last_downloaded_at',
            field=models.DateTimeField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
