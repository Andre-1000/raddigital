"""
Popula campos_formulario com todos os campos do formulario do RAD,
todos habilitados por padrao. Mudanca de negocio (17/07/2026):
"todos os campos devem ter a possibilidade de ser desabilitados".

Lista construida a partir da EFD (secoes 3.1 a 3.13) mais os campos
adicionados na mudanca de 17/07/2026.
"""
from django.db import migrations

CAMPOS = [
    ('numero_os', 'OS'),
    ('numero_sa', 'N° SA'),
    ('data_preenchimento', 'Data do RAD'),
    ('local_inicial', 'Local Inicial'),
    ('local_final', 'Local Final'),
    ('km_poste', 'Km/Poste'),
    ('linhas', 'Linhas'),
    ('vias', 'Vias'),
    ('tipo_manutencao', 'Tipo de Manutenção'),
    ('numero_falha', 'N° Falha'),
    ('hora_prog_inicio', 'Horário Programado de Início'),
    ('hora_prog_termino', 'Horário Programado de Término'),
    ('hora_real_inicio', 'Horário Real de Início'),
    ('hora_real_termino', 'Horário Real de Término'),
    ('motivo_atraso_inicio', 'Motivo do Atraso no Início'),
    ('desc_motivo_atraso_inicio', 'Descrição do Motivo do Atraso no Início'),
    ('motivo_atraso_termino', 'Motivo do Atraso no Término'),
    ('desc_motivo_atraso_termino', 'Descrição do Motivo do Atraso no Término'),
    ('servicos', 'Serviços Executados'),
    ('outros_servico_desc', 'Descrição de Outros Serviços'),
    ('materiais_utilizados', 'Materiais Utilizados'),
    ('observacoes_gerais', 'Observações Gerais'),
    ('colaboradores', 'Colaboradores/Participantes'),
    ('amv', 'Bloco AMV'),
    ('fotos_intervencao_verificada', 'Fotos — Intervenção Verificada'),
    ('fotos_acao_realizada', 'Fotos — Ação Realizada'),
    ('pdf', 'Anexo PDF'),
    ('responsavel_atividade', 'Responsável Atividade'),
    ('operador_ccm', 'Operador CCM'),
    ('descricao_tecnica_atividade', 'Descrição Técnica da Atividade'),
    ('equipes', 'Equipes Envolvidas'),
]


def popular_campos(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    for chave, rotulo in CAMPOS:
        CampoFormulario.objects.get_or_create(
            chave=chave, defaults={'rotulo': rotulo, 'habilitado': True}
        )


def remover_campos(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    CampoFormulario.objects.filter(chave__in=[c[0] for c in CAMPOS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('configuracoes', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(popular_campos, remover_campos),
    ]
