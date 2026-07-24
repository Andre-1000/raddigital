from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0007_rad_dispositivo'),
    ]

    operations = [
        migrations.AddField(
            model_name='rad',
            name='tipo_veiculo',
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='operador',
            field=models.TextField(null=True, blank=True),
        ),
    ]
