from django.db import migrations, models

# 30/07/2026: "Manutencao em AMV" ganha grupo proprio (AMV) em vez de
# ficar dentro de "Geral" -- alinhado com o novo suporte a multiplos
# blocos AMV por RAD (ver rad/migrations/0014).


def mover_amv_para_grupo_proprio(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.filter(nome='Manutenção em AMV').update(area='amv')


def reverter(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.filter(nome='Manutenção em AMV').update(area='geral')


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0009_grupos_corretiva_mecanizada'),
    ]

    operations = [
        migrations.AlterField(
            model_name='catservico',
            name='area',
            field=models.CharField(
                choices=[
                    ('geral', 'Geral'),
                    ('infra', 'Infra'),
                    ('corretiva', 'Corretiva'),
                    ('mecanizada', 'Mecanizada'),
                    ('amv', 'AMV'),
                ],
                default='geral',
                help_text='Agrupamento visual na tela de preenchimento (Geral, Infra, Corretiva, Mecanizada ou AMV).',
                max_length=10,
            ),
        ),
        migrations.RunPython(mover_amv_para_grupo_proprio, reverter),
    ]
