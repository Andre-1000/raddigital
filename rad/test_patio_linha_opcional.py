"""
30/10/2026: quando a UNICA Via marcada e "Pátio", a Linha fica opcional.
Pátio junto com outra via -> Linha obrigatoria (decisao do Andre).
"""
import json

import pytest
from django.urls import reverse

from catalogos.models import CatVia
from configuracoes.models import CampoFormulario
from rad.models import Rad
from rad.test_edicao_rad import _auth, _foto, tecnico  # noqa: F401
from rad.test_numero_os import _payload, catalogo  # noqa: F401


def _enviar(client, token, payload):
    return client.post(
        reverse('rad:sincronizar'),
        data={'dados': json.dumps(payload), 'fotos_intervencao_verificada': [_foto()]},
        **_auth(token),
    )


def _codigos(resposta, campo):
    return [e['codigo'] for e in resposta.json().get('erros', []) if e['campo'] == campo]


@pytest.fixture
def patio(db):
    return CatVia.objects.get_or_create(nome='Pátio')[0]


def test_so_patio_aceita_sem_linha(client, catalogo, tecnico, patio):  # noqa: F811
    _, token = tecnico
    resposta = _enviar(client, token, _payload(catalogo, vias=[patio.id], linhas=[]))
    assert resposta.status_code == 201, resposta.content
    assert Rad.objects.get().linhas.count() == 0


def test_so_patio_com_linha_tambem_aceita(client, catalogo, tecnico, patio):  # noqa: F811
    _, token = tecnico
    resposta = _enviar(client, token, _payload(catalogo, vias=[patio.id]))
    assert resposta.status_code == 201, resposta.content
    assert Rad.objects.get().linhas.count() == 1


def test_patio_com_outra_via_exige_linha(client, catalogo, tecnico, patio):  # noqa: F811
    _, token = tecnico
    resposta = _enviar(client, token, _payload(catalogo, vias=[catalogo['via'].id, patio.id], linhas=[]))
    assert resposta.status_code == 422
    assert 'VLD-007' in _codigos(resposta, 'linhas')


def test_sem_patio_exige_linha(client, catalogo, tecnico, patio):  # noqa: F811
    _, token = tecnico
    resposta = _enviar(client, token, _payload(catalogo, linhas=[]))
    assert 'VLD-007' in _codigos(resposta, 'linhas')


def test_config_obrigatorio_nao_trava_patio(client, catalogo, tecnico, patio):  # noqa: F811
    CampoFormulario.objects.update_or_create(
        chave='linhas', defaults={'rotulo': 'Linha', 'habilitado': True, 'obrigatorio': True},
    )
    _, token = tecnico
    resposta = _enviar(client, token, _payload(catalogo, vias=[patio.id], linhas=[]))
    assert resposta.status_code == 201, resposta.content
