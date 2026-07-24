from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0008_rad_tipo_veiculo_operador'),
    ]

    operations = [
        migrations.AddField(
            model_name='rad',
            name='terceiros_num_encarregados',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='terceiros_num_op_maquina',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='terceiros_num_ajudantes',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='terceiros_num_motorista',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='terceiros_volume',
            field=models.IntegerField(null=True, blank=True),
        ),
    ]
