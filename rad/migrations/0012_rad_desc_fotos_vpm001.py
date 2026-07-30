from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0011_amv_desc_outros'),
    ]

    operations = [
        migrations.AddField(
            model_name='rad',
            name='desc_foto_1',
            field=models.CharField(max_length=1000, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='desc_foto_2',
            field=models.CharField(max_length=1000, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='desc_foto_3',
            field=models.CharField(max_length=1000, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='desc_foto_4',
            field=models.CharField(max_length=1000, null=True, blank=True),
        ),
    ]
