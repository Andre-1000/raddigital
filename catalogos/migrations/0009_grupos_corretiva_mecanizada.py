from django.db import migrations, models

# 30/07/2026: dois grupos novos em Servicos Executados (Corretiva,
# Mecanizada), cada um com seus proprios servicos. Junto, 4 servicos
# antigos saem de circulacao (Esmerilhamento, Lubrificacao, Socaria,
# Ajuste) -- DESATIVADOS (ativo=FALSE), nao apagados, mesmo padrao ja
# usado para Limpeza/Controle de Vegetacao: RadServico tem FK PROTECT
# contra CatServico, entao um RAD antigo que citou um desses servicos
# quebraria se a linha fosse de fato removida do banco.

SERVICOS_NOVOS = [
    ('Topografia', 'corretiva'),
    ('Esmerilhadora', 'mecanizada'),
    ('Desguarnecedora', 'mecanizada'),
    ('Descarga de lastro', 'mecanizada'),
    ('Socadora', 'mecanizada'),
]

SERVICOS_DESATIVADOS = ['Esmerilhamento', 'Lubrificação', 'Socaria', 'Ajuste']


def criar_novos_e_desativar_antigos(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')

    for nome, area in SERVICOS_NOVOS:
        CatServico.objects.get_or_create(
            nome=nome,
            defaults={'area': area, 'ativo': True},
        )

    CatServico.objects.filter(nome__in=SERVICOS_DESATIVADOS).update(ativo=False)


def reverter(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.filter(
        nome__in=[nome for nome, _ in SERVICOS_NOVOS]
    ).delete()
    CatServico.objects.filter(nome__in=SERVICOS_DESATIVADOS).update(ativo=True)


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0008_servicos_area'),
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
                ],
                default='geral',
                help_text='Agrupamento visual na tela de preenchimento (Geral, Infra, Corretiva ou Mecanizada).',
                max_length=10,
            ),
        ),
        migrations.RunPython(criar_novos_e_desativar_antigos, reverter),
    ]
