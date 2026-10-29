"""
OS e N° SA com regra FIXA (29/10/2026).

Bug real: com a OS marcada como opcional em Configuracoes, um RAD sem OS
passava na validacao e o banco recusava (coluna NOT NULL) -> erro 500.

Regra nova (decisao do Andre):
  - OS obrigatoria em todo RAD, qualquer Tipo de Manutencao;
  - N° SA: obrigatoria em Preventiva/Preditiva, opcional em Corretiva,
    inativa em Falha (SA e Solicitante SA gravados vazios);
  - o Administrador nao altera OS nem SA em Configuracoes.
"""
import json

import pytest
from django.urls import reverse

from catalogos.models import CatTipoManutencao
from configuracoes.models import CampoFormulario
from rad.exportacao import gerar_mensagem_copiar
from rad.models import Rad
from rad.test_edicao_rad import _auth, _editar, _foto, admin, tecnico  # noqa: F401
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
def tipos(db):
    return {nome: CatTipoManutencao.objects.get_or_create(nome=nome)[0]
            for nome in ('Falha', 'Preventiva', 'Corretiva', 'Preditiva')}


@pytest.fixture
def config_aberta(db):
    """Simula producao com OS e SA marcadas como opcionais/desabilitadas."""
    for chave in ('numero_os', 'numero_sa'):
        CampoFormulario.objects.update_or_create(
            chave=chave, defaults={'rotulo': chave, 'obrigatorio': False, 'habilitado': True},
        )


class TestOsObrigatoria:
    def test_os_vazia_com_config_opcional_da_erro_claro_e_nao_500(
        self, client, catalogo, tecnico, config_aberta  # noqa: F811
    ):
        _, token = tecnico
        resposta = _enviar(client, token, _payload(catalogo, numero_os=None))
        assert resposta.status_code == 422
        assert 'VLD-001' in _codigos(resposta, 'numero_os')
        assert not Rad.objects.exists()

    def test_os_desabilitada_em_config_continua_exigida(self, client, catalogo, tecnico):  # noqa: F811
        CampoFormulario.objects.update_or_create(
            chave='numero_os', defaults={'rotulo': 'OS', 'habilitado': False},
        )
        _, token = tecnico
        resposta = _enviar(client, token, _payload(catalogo, numero_os=None))
        assert resposta.status_code == 422
        assert 'VLD-001' in _codigos(resposta, 'numero_os')


class TestSaPorTipo:
    @pytest.mark.parametrize('tipo', ['Preventiva', 'Preditiva'])
    def test_sa_obrigatoria(self, client, catalogo, tecnico, tipos, config_aberta, tipo):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(catalogo, id_tipo_manutencao=tipos[tipo].id, numero_sa=''))
        assert resposta.status_code == 422
        assert 'VLD-028' in _codigos(resposta, 'numero_sa')

    def test_corretiva_aceita_sa_vazia(self, client, catalogo, tecnico, tipos):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(catalogo, id_tipo_manutencao=tipos['Corretiva'].id, numero_sa=''))
        assert resposta.status_code == 201, resposta.content
        assert Rad.objects.get().numero_sa == ''

    def test_corretiva_com_sa_invalida_ainda_e_recusada(self, client, catalogo, tecnico, tipos):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(catalogo, id_tipo_manutencao=tipos['Corretiva'].id, numero_sa='12ab'))
        assert 'VLD-028' in _codigos(resposta, 'numero_sa')

    def test_falha_descarta_sa_e_solicitante(self, client, catalogo, tecnico, tipos):  # noqa: F811
        _, token = tecnico
        resposta = _enviar(client, token, _payload(
            catalogo, id_tipo_manutencao=tipos['Falha'].id, numero_falha=77,
            hora_prog_inicio=None, hora_prog_termino=None,
            numero_sa='12345', solicitante_sa='Fulano',  # ex.: app antigo em cache
        ))
        assert resposta.status_code == 201, resposta.content
        rad = Rad.objects.get()
        assert rad.numero_sa == ''
        assert rad.solicitante_sa is None
        mensagem = gerar_mensagem_copiar(rad)
        assert 'N° SA' not in mensagem and 'Solicitante SA' not in mensagem

    def test_editar_para_falha_apaga_a_sa(self, client, catalogo, tecnico, admin, tipos):  # noqa: F811
        _, token_tecnico = tecnico
        _enviar(client, token_tecnico, _payload(catalogo, id_tipo_manutencao=tipos['Preventiva'].id))
        rad = Rad.objects.get()
        assert rad.numero_sa == '35463'
        _, token = admin
        resposta = _editar(client, token, rad.numero_rad, _payload(
            catalogo, id_tipo_manutencao=tipos['Falha'].id, numero_falha=5,
            hora_prog_inicio=None, hora_prog_termino=None,
        ))
        assert resposta.status_code == 200, resposta.content
        rad.refresh_from_db()
        assert rad.numero_sa == ''

    def test_editar_de_falha_para_preventiva_exige_sa(self, client, catalogo, tecnico, admin, tipos):  # noqa: F811
        _, token_tecnico = tecnico
        _enviar(client, token_tecnico, _payload(
            catalogo, id_tipo_manutencao=tipos['Falha'].id, numero_falha=5,
            hora_prog_inicio=None, hora_prog_termino=None,
        ))
        rad = Rad.objects.get()
        _, token = admin
        resposta = _editar(client, token, rad.numero_rad, _payload(
            catalogo, id_tipo_manutencao=tipos['Preventiva'].id, numero_sa='',
        ))
        assert resposta.status_code == 422
        assert 'VLD-028' in _codigos(resposta, 'numero_sa')


class TestConfiguracoesTravadas:
    @pytest.mark.parametrize('chave', ['numero_os', 'numero_sa'])
    @pytest.mark.parametrize('acao', ['tornar_opcional', 'desabilitar_campo'])
    def test_admin_nao_altera(self, client, admin, config_aberta, chave, acao):  # noqa: F811
        _, token = admin
        resposta = client.post(reverse(f'configuracoes:{acao}', args=[chave]), **_auth(token))
        assert resposta.status_code == 409

    def test_lista_mostra_regra_fixa_como_obrigatoria(self, client, tecnico, config_aberta):  # noqa: F811
        _, token = tecnico
        campos = {c['chave']: c for c in client.get(reverse('configuracoes:listar_campos'), **_auth(token)).json()['campos']}
        for chave in ('numero_os', 'numero_sa'):
            assert campos[chave]['regra_fixa'] is True
            assert campos[chave]['obrigatorio'] is True
            assert campos[chave]['habilitado'] is True
        assert campos.get('responsavel_atividade', {}).get('regra_fixa', False) is False
