"""
30/10/2026 -- duas mudancas pedidas pelo Andre:

1) "Manutenção Corretiva em AMV" no bloco Corretiva: abre o Bloco AMV com
   as mesmas regras de "Manutenção em AMV", mas no maximo 3 blocos
   (1 inicial + 2 pelo botao). Com os dois servicos marcados vale o
   maior limite (16).
2) Operador CCO/CCM: na Abertura e na Entrega o tecnico marca se a
   pessoa e do CCO ou do CCM (opcional).
"""
import json

import pytest
from django.core.management import call_command
from django.urls import reverse

from catalogos.models import CatAcaoAmv, CatServico, CatTipoDefeitoAmv
from rad.edicao import montar_rascunho
from rad.exportacao import gerar_mensagem_copiar
from rad.exportacao_oficial import _operador_ccm_abertura_texto
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
def amv(db):
    defeito = CatTipoDefeitoAmv.objects.create(nome='Defeito Teste')
    acao = CatAcaoAmv.objects.create(nome='Acao Teste')
    return {
        'normal': CatServico.objects.create(nome='Manutencao AMV Teste', area='amv', requer_amv=True),
        'corretiva': CatServico.objects.create(
            nome='Manutencao Corretiva AMV Teste', area='corretiva', requer_amv=True, limite_blocos_amv=3,
        ),
        'bloco': {
            'mch_nao_cadastrada': True, 'desc_mch_nao_cadastrada': 'MCH 01',
            'tipos_defeito': [defeito.id], 'acoes': [acao.id],
        },
    }


class TestLimiteBlocosAmv:
    def test_corretiva_aceita_3_blocos(self, client, catalogo, tecnico, amv):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(
            catalogo, servicos=[amv['corretiva'].id], amv_blocos=[amv['bloco']] * 3,
        ))
        assert resposta.status_code == 201, resposta.content
        assert Rad.objects.get().amv_blocos.count() == 3

    def test_corretiva_recusa_4_blocos(self, client, catalogo, tecnico, amv):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(
            catalogo, servicos=[amv['corretiva'].id], amv_blocos=[amv['bloco']] * 4,
        ))
        assert resposta.status_code == 422
        assert 'VLD-020' in _codigos(resposta, 'amv_blocos')
        assert not Rad.objects.exists()

    def test_corretiva_exige_ao_menos_1_bloco(self, client, catalogo, tecnico, amv):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(catalogo, servicos=[amv['corretiva'].id], amv_blocos=[]))
        assert 'VLD-020' in _codigos(resposta, 'amv_blocos')

    def test_manutencao_em_amv_continua_com_16(self, client, catalogo, tecnico, amv):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(
            catalogo, servicos=[amv['normal'].id], amv_blocos=[amv['bloco']] * 16,
        ))
        assert resposta.status_code == 201, resposta.content

    def test_os_dois_marcados_vale_o_maior_limite(self, client, catalogo, tecnico, amv):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(
            catalogo, servicos=[amv['normal'].id, amv['corretiva'].id], amv_blocos=[amv['bloco']] * 5,
        ))
        assert resposta.status_code == 201, resposta.content

    def test_catalogo_entrega_o_limite_para_o_celular(self, client, tecnico, amv):  # noqa: F811
        _, token = tecnico
        servicos = client.get(reverse('catalogos:listar_todos'), **_auth(token)).json()['servicos']
        por_nome = {s['nome']: s for s in servicos}
        assert por_nome['Manutencao Corretiva AMV Teste']['limite_blocos_amv'] == 3
        assert por_nome['Manutencao AMV Teste']['limite_blocos_amv'] is None


@pytest.mark.django_db
def test_seed_cria_o_servico_na_corretiva():
    call_command('carregar_catalogos')
    call_command('carregar_catalogos')  # roda a cada deploy: nao pode duplicar
    novo = CatServico.objects.get(nome='Manutenção Corretiva em AMV')
    assert (novo.area, novo.requer_amv, novo.limite_blocos_amv, novo.ativo) == ('corretiva', True, 3, True)
    antigo = CatServico.objects.get(nome='Manutenção em AMV')
    assert (antigo.area, antigo.limite_blocos_amv) == ('amv', None)


class TestOperadorCcoCcm:
    def test_grava_cco_e_ccm(self, client, catalogo, tecnico):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(
            catalogo,
            operador_ccm_abertura_nome='Fulano', operador_ccm_abertura_hora='08:00',
            operador_ccm_abertura_centro='CCO',
            operador_ccm_entrega_nome='Beltrano', operador_ccm_entrega_hora='17:00',
            operador_ccm_entrega_centro='CCM',
        ))
        assert resposta.status_code == 201, resposta.content
        rad = Rad.objects.get()
        assert (rad.operador_ccm_abertura_centro, rad.operador_ccm_entrega_centro) == ('CCO', 'CCM')
        mensagem = gerar_mensagem_copiar(rad)
        assert 'Operador CCO/CCM - Abertura: Fulano (08:00) – CCO' in mensagem
        assert 'Operador CCO/CCM - Entrega: Beltrano (17:00) – CCM' in mensagem
        assert _operador_ccm_abertura_texto(rad) == 'Fulano (08:00) – CCO'
        rascunho = montar_rascunho(rad)
        assert (rascunho['operador_ccm_abertura_centro'], rascunho['operador_ccm_entrega_centro']) == ('CCO', 'CCM')

    def test_opcional(self, client, catalogo, tecnico):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(catalogo, operador_ccm_abertura_nome='Fulano'))
        assert resposta.status_code == 201, resposta.content
        rad = Rad.objects.get()
        assert rad.operador_ccm_abertura_centro is None and rad.operador_ccm_entrega_centro is None
        assert ' – CC' not in gerar_mensagem_copiar(rad)

    def test_valor_invalido_e_recusado(self, client, catalogo, tecnico):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(catalogo, operador_ccm_abertura_centro='XYZ'))
        assert resposta.status_code == 422
        assert 'VLD-030' in _codigos(resposta, 'operador_ccm_abertura_centro')
