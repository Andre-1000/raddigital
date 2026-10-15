from django.db import migrations, models

# 14/10/2026: novo bloco "Inspeção e Ronda" (area 'insp_ronda') em
# Servicos Executados, com os servicos "Inspeção" e "Reparo".
#
# Decisao de negocio (opcao D): os servicos "Inspeção" e "Reparo" que
# ja existiam no bloco Geral NAO mudam de grupo -- sao RENOMEADOS para
# "Inspeção (Geral)" e "Reparo (Geral)" e DESATIVADOS. Assim os RADs
# antigos (que apontam para eles por FK) continuam no Geral, sem
# mudar o historico; a reclassificacao dos que forem de ronda sera
# feita depois, caso a caso.
#
# Os novos "Inspeção" e "Reparo" nascem na area 'insp_ronda', simples
# (sem bloco extra), com a mesma descricao dos antigos.
#
# Ordem importa: o start.sh roda migrate ANTES do seed
# (carregar_catalogos). Se o seed rodasse antes, o UPSERT por nome
# apenas moveria os antigos de grupo (era a opcao A, descartada).

NOMES = [
    ('Inspeção', 'Inspeção (Geral)'),
    ('Reparo', 'Reparo (Geral)'),
]


def aplicar(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    for nome_original, nome_antigo in NOMES:
        # Idempotente: se ja foi renomeado (ex.: banco restaurado), nao
        # renomeia de novo.
        if CatServico.objects.filter(nome=nome_antigo).exists():
            antigo = CatServico.objects.get(nome=nome_antigo)
        else:
            antigo = CatServico.objects.filter(nome=nome_original, area='geral').first()
            if antigo is not None:
                antigo.nome = nome_antigo
                antigo.ativo = False
                antigo.save(update_fields=['nome', 'ativo'])

        descricao = antigo.descricao if antigo is not None else None
        novo, criado = CatServico.objects.get_or_create(
            nome=nome_original,
            defaults={'area': 'insp_ronda', 'descricao': descricao, 'ativo': True},
        )
        if not criado and novo.area != 'insp_ronda':
            novo.area = 'insp_ronda'
            novo.ativo = True
            novo.save(update_fields=['area', 'ativo'])


def reverter(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    RadServico = apps.get_model('rad', 'RadServico')
    for nome_original, nome_antigo in NOMES:
        novo = CatServico.objects.filter(nome=nome_original, area='insp_ronda').first()
        if novo is not None:
            if RadServico.objects.filter(servico=novo).exists():
                raise RuntimeError(
                    f'Nao e possivel desfazer: ja existem RADs com o servico '
                    f'"{nome_original}" do bloco Inspeção e Ronda.'
                )
            novo.delete()
        CatServico.objects.filter(nome=nome_antigo).update(
            nome=nome_original, ativo=True, area='geral'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0012_inspecao_canaleta'),
        ('rad', '0028_horarios_programados_opcionais'),
    ]

    operations = [
        migrations.AlterField(
            model_name='catservico',
            name='area',
            field=models.CharField(
                choices=[
                    ('amv', 'AMV'),
                    ('corretiva', 'Corretiva'),
                    ('geral', 'Geral'),
                    ('infra', 'Infra'),
                    ('insp_ronda', 'Inspeção e Ronda'),
                    ('mecanizada', 'Mecanizada'),
                ],
                default='geral',
                help_text='Agrupamento visual na tela de preenchimento (AMV, Corretiva, Geral, Infra, Inspeção e Ronda ou Mecanizada).',
                max_length=10,
            ),
        ),
        migrations.RunPython(aplicar, reverter),
    ]
