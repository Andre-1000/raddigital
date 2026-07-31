"""
30/07/2026: o campo configuravel 'operador_ccm' (Habilitar/Obrigatorio
na tela de Configuracoes) e substituido por dois campos independentes,
acompanhando a divisao do Operador CCM em Abertura/Entrega no
formulario (ver rad/models.py). Se o Administrador ja tinha
desabilitado ou tornado obrigatorio o campo antigo, esse estado e
copiado para os dois novos -- nao se perde a configuracao existente.
"""
from django.db import migrations


def migrar_campo(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    antigo = CampoFormulario.objects.filter(chave='operador_ccm').first()
    habilitado = antigo.habilitado if antigo else True
    obrigatorio = antigo.obrigatorio if antigo else False

    CampoFormulario.objects.get_or_create(
        chave='operador_ccm_abertura',
        defaults={
            'rotulo': 'Op CCM - Abertura',
            'habilitado': habilitado,
            'obrigatorio': obrigatorio,
        },
    )
    CampoFormulario.objects.get_or_create(
        chave='operador_ccm_entrega',
        defaults={
            'rotulo': 'Op CCM - Entrega',
            'habilitado': habilitado,
            'obrigatorio': obrigatorio,
        },
    )
    if antigo:
        antigo.delete()


def reverter(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    novo = CampoFormulario.objects.filter(chave='operador_ccm_abertura').first()
    habilitado = novo.habilitado if novo else True
    obrigatorio = novo.obrigatorio if novo else False

    CampoFormulario.objects.get_or_create(
        chave='operador_ccm',
        defaults={
            'rotulo': 'Operador CCM',
            'habilitado': habilitado,
            'obrigatorio': obrigatorio,
        },
    )
    CampoFormulario.objects.filter(
        chave__in=['operador_ccm_abertura', 'operador_ccm_entrega']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('configuracoes', '0004_flag_exportar_pdf'),
    ]

    operations = [
        migrations.RunPython(migrar_campo, reverter),
    ]
