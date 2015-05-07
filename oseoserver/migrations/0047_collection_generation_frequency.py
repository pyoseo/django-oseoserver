# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0046_auto_20150507_0941'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='generation_frequency',
            field=models.CharField(default=b'once per hour', help_text=b'Frequency at which new products get generated', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
