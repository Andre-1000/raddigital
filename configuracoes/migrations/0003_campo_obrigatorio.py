"""
Adiciona o campo 'obrigatorio' e define os valores iniciais
correspondentes ao comportamento ja implementado hoje (hardcoded) em
rad/validadores.py -- para que ligar esta funcionalidade nao mude o
comportamento atual do formulario ate que um Administrador altere
algo explicitamente.

Campos com obrigatoriedade CONDICIONAL (dependem de outro campo, ex.:
N. Falha so quando Tipo=Falha) entram aqui com o valor False -- o
toggle funciona como uma sobreposicao "forcar sempre obrigatorio" para
esses casos, nao como o comportamento condicional em si (que continua
funcionando normalmente por baixo).
"""
from django.db import migrations, models

# Campos hoje sempre obrigatorios (VLD-001 a VLD-029, sem condicao).
CHAVES_OBRIGATORIAS_POR_PADRAO = {
    'numero_os',
    'numero_sa',
    'data_preenchimento',
    'local_inicial',
    'local_final',
    'linhas',
    'vias',
    'tipo_manutencao',
    'hora_prog_inicio',
    'hora_prog_termino',
    'hora_real_inicio',
    'hora_real_termino',
    'servicos',
    'colaboradores',
    'responsavel_atividade',
}


def definir_obrigatoriedade_padrao(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    for campo in CampoFormulario.objects.all():
        campo.obrigatorio = campo.chave in CHAVES_OBRIGATORIAS_POR_PADRAO
        campo.save(update_fields=['obrigatorio'])


def reverter(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    CampoFormulario.objects.all().update(obrigatorio=False)


class Migration(migrations.Migration):

    dependencies = [
        ('configuracoes', '0002_popular_campos_formulario'),
    ]

    operations = [
        migrations.AddField(
            model_name='campoformulario',
            name='obrigatorio',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Sobrepoe a regra de obrigatoriedade padrao do campo (22/07/2026). '
                    'So tem efeito quando habilitado=True.'
                ),
            ),
        ),
        migrations.RunPython(definir_obrigatoriedade_padrao, reverter),
    ]
