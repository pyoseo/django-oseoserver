# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0047_collection_generation_frequency'),
    ]

    operations = [
        migrations.CreateModel(
            name='Extension',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('xml_fragment', models.TextField(help_text=b'Custom extensions to the OSEO standard')),
                ('item', models.ForeignKey(to='oseoserver.CustomizableItem')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
