# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0045_auto_20150505_1123'),
    ]

    operations = [
        migrations.AlterField(
            model_name='itemprocessor',
            name='python_path',
            field=models.CharField(default=b'oseoserver.orderpreparation.exampleorderprocessor.ExampleOrderProcessor', help_text=b'Python import path to a custom class that is used to process the order items. This class must conform to the expected interface.', max_length=255),
            preserve_default=True,
        ),
    ]
