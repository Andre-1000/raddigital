from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0009_rad_terceiros'),
    ]

    operations = [
        migrations.AddField(
            model_name='rad',
            name='solicitante_sa',
            field=models.TextField(null=True, blank=True),
        ),
    ]
