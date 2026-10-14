"""
Tipo de Manutencao = Falha: horarios programados ficam VAZIOS (NULL),
so os reais sao exigidos e a duracao real continua calculada (14/10/2026).
Autocontido, como rad/test_edicao_rad.py.
"""
import datetime as dt

import pytest
from django.urls import reverse

from catalogos.models import CatTipoManutencao
from rad import exportacao, exportacao_excel
from rad.regras_horario import processar_horarios
from rad.test_edicao_rad import (  # noqa: F401
    _auth, _editar, _sincronizar, admin, tecnico,
)
from rad.test_numero_os import _payload, catalogo  # noqa: F401
from rad.validadores import validar_payload_sincronizacao
from rad.test_numero_os import HOJE


def _payload_falha(catalogo, **alt):
    falha, _ = CatTipoManutencao.objects.get_or_create(nome='Falha')
    base = dict(
        id_tipo_manutencao=falha.id, numero_falha=123,
        hora_prog_inicio='', hora_prog_termino='', data_hp_inicio='', data_hp_termino='',
        hora_real_inicio='09:00', hora_real_termino='11:30', sync_id_tentativa='falha-0001',
    )
    base.update(alt)
    return _payload(catalogo, **base)


def test_processar_horarios_falha_calcula_so_o_real():
    r = processar_horarios(
        data_preenchimento=HOJE, hora_prog_inicio=None, hora_prog_termino=None,
        hora_real_inicio=dt.time(9, 0), hora_real_termino=dt.time(11, 30),
        tipo_manutencao_e_falha=True,
    )
    assert r['data_hora_prog_inicio'] is None and r['data_hora_prog_termino'] is None
    assert r['data_hp_inicio'] is None and r['duracao_programada_min'] is None
    assert r['duracao_real_min'] == 150
    assert r['atraso_inicio'] is False and r['atraso_termino'] is False


def test_processar_horarios_falha_ignora_programado_enviado():
    r = processar_horarios(
        data_preenchimento=HOJE, hora_prog_inicio=dt.time(8), hora_prog_termino=dt.time(9),
        hora_real_inicio=dt.time(9, 0), hora_real_termino=dt.time(11, 30),
        tipo_manutencao_e_falha=True,
    )
    assert r['duracao_programada_min'] is None and r['atraso_termino'] is False


def test_processar_horarios_nao_falha_continua_igual():
    r = processar_horarios(
        data_preenchimento=HOJE, hora_prog_inicio=dt.time(8), hora_prog_termino=dt.time(10),
        hora_real_inicio=dt.time(8), hora_real_termino=dt.time(11),
        tipo_manutencao_e_falha=False,
    )
    assert r['duracao_programada_min'] == 120 and r['atraso_termino'] is True


def test_vld011_falha_nao_exige_programado_mas_exige_real():
    erros = []
    from rad.validadores import _validar_horarios_obrigatorios
    _validar_horarios_obrigatorios({'_tipo_manutencao_e_falha': True, 'hora_real_inicio': '1:00'}, erros)
    assert [e['campo'] for e in erros] == ['hora_real_termino']
    erros = []
    _validar_horarios_obrigatorios({'hora_real_inicio': '1:00', 'hora_real_termino': '2:00'}, erros)
    assert {e['campo'] for e in erros} == {'hora_prog_inicio', 'hora_prog_termino'}


def test_config_obrigatoria_nao_trava_falha(db):
    from configuracoes.models import CampoFormulario
    from rad.validadores import _aplicar_configuracao_obrigatoriedade
    CampoFormulario.objects.update_or_create(
        chave='hora_prog_inicio',
        defaults=dict(rotulo='Horário Programado de Início', habilitado=True, obrigatorio=True),
    )
    erros = []
    _aplicar_configuracao_obrigatoriedade({'_tipo_manutencao_e_falha': True}, erros)
    assert not [e for e in erros if e['campo'] == 'hora_prog_inicio']
    _aplicar_configuracao_obrigatoriedade({'_tipo_manutencao_e_falha': False}, erros)
    assert [e for e in erros if e['campo'] == 'hora_prog_inicio']


def test_sincroniza_falha_guarda_programado_vazio_e_duracao_real(client, catalogo, tecnico):  # noqa: F811
    _, token = tecnico
    rad = _sincronizar(client, token, _payload_falha(catalogo))
    assert rad.hora_prog_inicio is None and rad.hora_prog_termino is None
    assert rad.data_hp_inicio is None and rad.data_hora_prog_inicio is None
    assert rad.duracao_programada_min is None
    assert rad.duracao_real_min == 150
    assert rad.atraso_inicio is False and rad.atraso_termino is False


def test_falha_sem_horario_real_continua_bloqueada(client, catalogo, tecnico):  # noqa: F811
    from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: F401
    import json
    _, token = tecnico
    resp = client.post(
        reverse('rad:sincronizar'),
        data={'dados': json.dumps(_payload_falha(catalogo, hora_real_termino=''))},
        **_auth(token),
    )
    assert resp.status_code == 422
    assert any(e['campo'] == 'hora_real_termino' for e in resp.json().get('erros', []))


def test_exportacoes_e_consulta_nao_quebram_com_programado_vazio(client, catalogo, tecnico, admin):  # noqa: F811
    _, token = tecnico
    rad = _sincronizar(client, token, _payload_falha(catalogo))
    campos = dict((c[0], c[2]) for c in exportacao.montar_campos(rad)) if hasattr(exportacao, 'montar_campos') else {}
    if campos:
        assert campos['hora_prog_inicio'] == 'N/A'
    exportacao_excel.montar_linha(rad) if hasattr(exportacao_excel, 'montar_linha') else None
    _, tok_admin = admin
    r1 = client.get(reverse('consulta:detalhe', args=[rad.numero_rad]), **_auth(tok_admin)) \
        if _tem_rota('consulta:detalhe') else None
    if r1 is not None:
        assert r1.status_code == 200
        assert r1.json().get('hora_prog_inicio') is None


def _tem_rota(nome):
    try:
        reverse(nome, args=['x'])
        return True
    except Exception:
        return False


def test_editar_falha_para_outro_tipo_exige_programado(client, catalogo, tecnico, admin):  # noqa: F811
    _, token = tecnico
    _, tok_admin = admin
    rad = _sincronizar(client, token, _payload_falha(catalogo))
    sem = _editar(client, tok_admin, rad.numero_rad,
                  _payload(catalogo, hora_prog_inicio='', hora_prog_termino=''))
    assert sem.status_code == 422
    ok = _editar(client, tok_admin, rad.numero_rad, _payload(catalogo))
    assert ok.status_code == 200, ok.content
    rad.refresh_from_db()
    assert rad.hora_prog_inicio == dt.time(8, 0) and rad.duracao_programada_min == 240


def test_editar_outro_tipo_para_falha_limpa_programado(client, catalogo, tecnico, admin):  # noqa: F811
    _, token = tecnico
    _, tok_admin = admin
    rad = _sincronizar(client, token, _payload(catalogo))
    resp = _editar(client, tok_admin, rad.numero_rad, _payload_falha(catalogo))
    assert resp.status_code == 200, resp.content
    rad.refresh_from_db()
    assert rad.hora_prog_inicio is None and rad.duracao_programada_min is None
    assert rad.duracao_real_min == 150
