"""
Coluna "Serviços" da exportacao (planilha do Google + Excel do
Dashboard e da Consulta) no formato "Área > Serviço" -- 15/10/2026,
para o BI-RAD conseguir analisar por area. Autocontido, como
rad/test_falha_sem_horario_programado.py.
"""
from catalogos.models import CatServico
from rad import exportacao_excel
from rad.exportacao_excel import _rotulo_area
from rad.google_sheets import montar_linha
from rad.test_edicao_rad import _sincronizar, tecnico  # noqa: F401
from rad.test_numero_os import _payload, catalogo  # noqa: F401


def _indice_servicos():
    return [chave for chave, _ in exportacao_excel.COLUNAS].index('servicos')


def test_rotulo_area_usa_o_rotulo_da_tela():
    assert _rotulo_area('insp_ronda') == 'Inspeção e Ronda'
    assert _rotulo_area('geral') == 'Geral'


def test_rotulo_area_nunca_quebra():
    assert _rotulo_area('') == 'Sem área'
    assert _rotulo_area(None) == 'Sem área'
    assert _rotulo_area('nova_area') == 'nova_area'


def test_planilha_traz_area_de_cada_servico(client, catalogo, tecnico):  # noqa: F811
    _, token = tecnico
    servico_infra = CatServico.objects.create(nome='Teste Area Infra', area='infra')
    rad = _sincronizar(
        client, token,
        _payload(catalogo, servicos=[catalogo['servico'].id, servico_infra.id], sync_id_tentativa='area-0001'),
    )

    celula = montar_linha(rad)[_indice_servicos()]

    itens = sorted(celula.split('; '))
    assert itens == ['Geral > Inspecao', 'Infra > Teste Area Infra']


def test_par_area_servico_nao_descasa_ao_dividir(client, catalogo, tecnico):  # noqa: F811
    """O que o Power Query vai fazer: dividir por '; ' e depois por ' > '."""
    _, token = tecnico
    ronda = CatServico.objects.create(nome='Teste Ronda', area='insp_ronda')
    rad = _sincronizar(
        client, token,
        _payload(catalogo, servicos=[ronda.id], sync_id_tentativa='area-0002'),
    )

    celula = montar_linha(rad)[_indice_servicos()]
    area, servico = celula.split(exportacao_excel.SEPARADOR_AREA)

    assert (area, servico) == ('Inspeção e Ronda', 'Teste Ronda')


def test_excel_gera_com_area(client, catalogo, tecnico):  # noqa: F811
    from io import BytesIO
    from openpyxl import load_workbook

    _, token = tecnico
    rad = _sincronizar(client, token, _payload(catalogo, sync_id_tentativa='area-0003'))

    planilha = load_workbook(BytesIO(exportacao_excel.gerar_excel_bytes([rad]))).active
    assert planilha.cell(row=2, column=_indice_servicos() + 1).value == 'Geral > Inspecao'
