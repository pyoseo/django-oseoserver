# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oseoserver', '0039_auto_20150210_1654'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionBatch',
            fields=[
                ('batch_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='oseoserver.Batch')),
                ('timeslot', models.DateTimeField()),
                ('collection', models.ForeignKey(to='oseoserver.Collection')),
            ],
            options={
            },
            bases=('oseoserver.batch',),
        ),
    ]
