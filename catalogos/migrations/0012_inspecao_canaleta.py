from django.db import migrations, models

# 30/07/2026: campo requer_canaleta (abre o bloco "Anomalias" no
# formulario) + criacao do servico "Inspeção de Canaleta" (area
# infra), mesmo padrao ja usado em 0011_inspecoes_e_renomeacao.py.


def aplicar(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.get_or_create(
        nome='Inspeção de Canaleta',
        defaults={'area': 'infra', 'requer_canaleta': True, 'ativo': True},
    )


def reverter(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.filter(nome='Inspeção de Canaleta').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0011_inspecoes_e_renomeacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='catservico',
            name='requer_canaleta',
            field=models.BooleanField(
                default=False,
                help_text='TRUE somente para Inspeção de Canaleta -- abre o bloco Anomalias.',
            ),
        ),
        migrations.RunPython(aplicar, reverter),
    ]
