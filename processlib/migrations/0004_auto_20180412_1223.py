# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('processlib', '0003_auto_20180412_1157'),
    ]

    operations = [
        migrations.AddField(
            model_name='activityinstance',
            name='assigned_group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='auth.Group', null=True),
        ),
        migrations.AddField(
            model_name='activityinstance',
            name='assigned_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True),
        ),
    ]
