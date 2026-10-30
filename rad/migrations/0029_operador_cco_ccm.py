from django.db import migrations, models

# 30/10/2026: Operador CCO/CCM -- a pessoa informada na Abertura/Entrega
# pode ser do CCO ou do CCM. Dois campos novos, opcionais (vazio = nao
# informado). RADs antigos ficam vazios; nenhum dado existente muda.
#
# Tambem renomeia o rotulo exibido na tela de Configuracoes
# ("Op CCM - Abertura" -> "Operador CCO/CCM - Abertura", idem Entrega).
# Reversao devolve o rotulo antigo.

ROTULOS = [
    ('operador_ccm_abertura', 'Op CCM - Abertura', 'Operador CCO/CCM - Abertura'),
    ('operador_ccm_entrega', 'Op CCM - Entrega', 'Operador CCO/CCM - Entrega'),
]


def renomear_rotulos(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    for chave, _antigo, novo in ROTULOS:
        CampoFormulario.objects.filter(chave=chave).update(rotulo=novo)


def voltar_rotulos(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    for chave, antigo, _novo in ROTULOS:
        CampoFormulario.objects.filter(chave=chave).update(rotulo=antigo)


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0028_horarios_programados_opcionais'),
        ('configuracoes', '0006_limite_fotos'),
    ]

    operations = [
        migrations.AddField(
            model_name='rad',
            name='operador_ccm_abertura_centro',
            field=models.CharField(
                blank=True,
                choices=[('CCO', 'CCO'), ('CCM', 'CCM')],
                max_length=3,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='rad',
            name='operador_ccm_entrega_centro',
            field=models.CharField(
                blank=True,
                choices=[('CCO', 'CCO'), ('CCM', 'CCM')],
                max_length=3,
                null=True,
            ),
        ),
        migrations.RunPython(renomear_rotulos, voltar_rotulos),
    ]
