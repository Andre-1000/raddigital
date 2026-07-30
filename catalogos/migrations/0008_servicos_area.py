from django.db import migrations, models

# 30/07/2026: agrupamento visual "Geral" vs "Infra" na tela de Servicos
# Executados. A area e derivada automaticamente de requer_terceiros --
# os 4 servicos terceirizados (Recolhimento de Lixo, Limpeza de
# Canaleta, Capina Quimica, Rocada/Poda) sao exatamente os de area
# 'infra'. Nenhum dado digitado a mao, sem risco de divergencia.


def marcar_area_infra(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.filter(requer_terceiros=True).update(area='infra')


def reverter(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.all().update(area='geral')


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0007_vpm001'),
    ]

    operations = [
        migrations.AddField(
            model_name='catservico',
            name='area',
            field=models.CharField(
                choices=[('geral', 'Geral'), ('infra', 'Infra')],
                default='geral',
                help_text='Agrupamento visual na tela de preenchimento (Geral ou Infra).',
                max_length=10,
            ),
        ),
        migrations.RunPython(marcar_area_infra, reverter),
    ]
