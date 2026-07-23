from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0006_rad_descricao_tecnica_atividade_rad_operador_ccm_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rad',
            name='dispositivo',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('desktop', 'Computador'),
                    ('mobile', 'Celular'),
                    ('desconhecido', 'Desconhecido'),
                ],
                default='desconhecido',
                help_text='Detectado automaticamente pelo navegador usado na sincronizacao.',
            ),
        ),
    ]
