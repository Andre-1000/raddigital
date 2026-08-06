from django.db import migrations

# 30/07/2026: dois servicos novos (Inspecao Corretiva no grupo
# Corretiva, Inspecao AMV no grupo AMV) e uma renomeacao -- "Recolhimento
# de Lixo" passa a se chamar "Recolhimento de Descartes". E uma
# renomeacao DE VERDADE (mesma linha, mesmo id), nao desativar uma e
# criar outra -- assim RADs antigos que ja usaram esse servico
# continuam com a FK intacta, e so o texto exibido muda.


def aplicar(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')

    CatServico.objects.filter(nome='Recolhimento de Lixo').update(nome='Recolhimento de Descartes')

    CatServico.objects.get_or_create(
        nome='Inspeção Corretiva',
        defaults={'area': 'corretiva', 'ativo': True},
    )
    CatServico.objects.get_or_create(
        nome='Inspeção AMV',
        defaults={'area': 'amv', 'ativo': True},
    )


def reverter(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.filter(nome='Recolhimento de Descartes').update(nome='Recolhimento de Lixo')
    CatServico.objects.filter(nome__in=['Inspeção Corretiva', 'Inspeção AMV']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0010_grupo_amv'),
    ]

    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
