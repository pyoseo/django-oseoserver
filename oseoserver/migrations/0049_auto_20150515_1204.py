# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0048_extension'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='extension',
            name='xml_fragment',
        ),
        migrations.AddField(
            model_name='extension',
            name='text',
            field=models.CharField(help_text=b'Custom extensions to the OSEO standard', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
