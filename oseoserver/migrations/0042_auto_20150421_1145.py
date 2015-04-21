# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0041_auto_20150417_1612'),
    ]

    operations = [
        migrations.AddField(
            model_name='option',
            name='multiple_entries',
            field=models.BooleanField(default=False, help_text=b'Can this option have multiple selections?'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='paymentoption',
            name='multiple_entries',
            field=models.BooleanField(default=False, help_text=b'Can this option have multiple selections?'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sceneselectionoption',
            name='multiple_entries',
            field=models.BooleanField(default=False, help_text=b'Can this option have multiple selections?'),
            preserve_default=True,
        ),
    ]
