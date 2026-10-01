"""
Testes da OS de 11 digitos e da regra do campo "opcional" (30/09/2026).

Contexto: um RAD com OS 71000006649 (11 digitos) nao sincronizava -- o
formulario so mostrava "Erro inesperado ao sincronizar" (HTTP 500).
Duas causas combinadas:
  1. O banco guardava a OS em IntegerField (ate ~2,1 bilhoes) e a trava
     de numeracao por OS usava pg_advisory_xact_lock(int, int), que nao
     aceita numero desse tamanho.
  2. Com a OS marcada como "opcional" em Configuracoes, o sistema
     apagava TODOS os erros de validacao da OS -- inclusive o de
     tamanho -- e o numero chegava ate o banco.

Este arquivo e autocontido (monta o proprio payload completo) de
proposito: boa parte da suite antiga esta desatualizada em relacao aos
campos obrigatorios de hoje (Data da Atividade, Km/Poste Inicial/Final).
"""
import datetime
import io
import json

import pytest
from django.urls import reverse
from PIL import Image

from catalogos.models import CatEquipe, CatLinha, CatLocal, CatServico, CatTipoManutencao, CatVia
from configuracoes.models import CampoFormulario
from rad.models import Rad
from rad.regras_negocio import gerar_numero_execucao
from rad.views import _normalizar_payload
from rad.validadores import LIMITE_DIGITOS_OS, validar_payload_sincronizacao
from usuarios.models import Token, Usuario

OS_REAL_DE_11_DIGITOS = 71000006649
HOJE = datetime.date.today()


@pytest.fixture
def catalogo(db):
    return {
        'local': CatLocal.objects.create(sigla='PTR', nome='Patio Teste', categoria='estacao'),
        'linha': CatLinha.objects.create(codigo='11', nome='Coral'),
        'via': CatVia.objects.create(nome='Via 1'),
        'tipo': CatTipoManutencao.objects.create(nome='Preventiva'),
        'equipe_vp': CatEquipe.objects.get_or_create(codigo='VP', defaults={'nome': 'VP'})[0],
        'servico': CatServico.objects.create(nome='Inspecao'),
    }


@pytest.fixture
def usuario_com_token(db):
    usuario = Usuario.objects.create(login='tecnico.os')
    token = Token.gerar_para(usuario)
    return usuario, token


def _payload(catalogo, **alteracoes):
    """Payload COMPLETO e valido (exceto pelo que for alterado em `alteracoes`)."""
    dados = {
        'numero_os': 4321,
        'numero_sa': '35463',
        'data_preenchimento': HOJE.isoformat(),
        'data_atividade': HOJE.isoformat(),
        'id_local_inicial': catalogo['local'].sigla,
        'id_local_final': catalogo['local'].sigla,
        'km_poste_inicial': '12/03',
        'km_poste_final': '12/06',
        'linhas': [catalogo['linha'].codigo],
        'vias': [catalogo['via'].id],
        'id_tipo_manutencao': catalogo['tipo'].id,
        'numero_falha': None,
        'hora_prog_inicio': '08:00',
        'hora_prog_termino': '12:00',
        'hora_real_inicio': '08:00',
        'hora_real_termino': '12:00',
        'servicos': [catalogo['servico'].id],
        'colaboradores': [{'registro_empresa': None, 'nome': 'Participante Um', 'tipo': 'participante'}],
        'responsavel_atividade': 'Responsavel Teste',
        'sync_id_tentativa': 'os-teste-0001',
    }
    dados.update(alteracoes)
    return dados


def _foto():
    from django.core.files.uploadedfile import SimpleUploadedFile

    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), color='green').save(buffer, format='JPEG')
    return SimpleUploadedFile('foto.jpg', buffer.getvalue(), content_type='image/jpeg')


def _sincronizar(client, token, payload):
    return client.post(
        reverse('rad:sincronizar'),
        data={'dados': json.dumps(payload), 'fotos_intervencao_verificada': [_foto()]},
        HTTP_AUTHORIZATION=f'Token {token.valor_plano}',
    )


def _codigos_do_campo(erros, campo):
    return [e['codigo'] for e in erros if e['campo'] == campo]


def _validar(payload):
    # A view converte as datas de texto para date antes de validar
    # (rad/views.py::_normalizar_payload) -- aqui repetimos o mesmo passo.
    return validar_payload_sincronizacao(_normalizar_payload(payload), hoje=HOJE)


def _tornar_os_opcional():
    CampoFormulario.objects.update_or_create(
        chave='numero_os', defaults={'rotulo': 'OS', 'habilitado': True, 'obrigatorio': False}
    )


# ---------------------------------------------------------------------------
# Sincronizacao de ponta a ponta com a OS real do RAD que falhava
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSincronizacaoComOsDe11Digitos:
    def test_os_de_11_digitos_sincroniza_e_grava_o_valor_exato(self, client, catalogo, usuario_com_token):
        _, token = usuario_com_token
        resposta = _sincronizar(
            client, token, _payload(catalogo, numero_os=OS_REAL_DE_11_DIGITOS)
        )

        assert resposta.status_code == 201, resposta.content
        assert resposta.json()['numero_os'] == OS_REAL_DE_11_DIGITOS
        assert Rad.objects.get().numero_os == OS_REAL_DE_11_DIGITOS

    def test_numero_de_execucao_funciona_para_a_mesma_os_grande(self, client, catalogo, usuario_com_token):
        """Dois RADs da mesma OS de 11 digitos recebem execucao 1 e 2 (a trava por OS continua valendo)."""
        _, token = usuario_com_token
        r1 = _sincronizar(client, token, _payload(catalogo, numero_os=OS_REAL_DE_11_DIGITOS, sync_id_tentativa='a'))
        r2 = _sincronizar(client, token, _payload(catalogo, numero_os=OS_REAL_DE_11_DIGITOS, sync_id_tentativa='b'))

        assert (r1.status_code, r2.status_code) == (201, 201)
        assert [r1.json()['numero_execucao'], r2.json()['numero_execucao']] == [1, 2]

    def test_os_de_12_digitos_e_recusada_com_mensagem_clara_nao_com_erro_500(
        self, client, catalogo, usuario_com_token
    ):
        _, token = usuario_com_token
        resposta = _sincronizar(client, token, _payload(catalogo, numero_os=100_000_000_000))

        assert resposta.status_code == 422
        mensagens = [e['mensagem'] for e in resposta.json()['erros'] if e['campo'] == 'numero_os']
        assert mensagens == [f'A OS deve ter no maximo {LIMITE_DIGITOS_OS} digitos.']
        assert Rad.objects.count() == 0

    def test_os_de_12_digitos_continua_recusada_com_a_os_OPCIONAL(self, client, catalogo, usuario_com_token):
        """
        O caso exato do erro 500 original: OS opcional + numero grande demais.
        Antes da correcao o numero passava pela validacao e estourava no banco.
        """
        _tornar_os_opcional()
        _, token = usuario_com_token
        resposta = _sincronizar(client, token, _payload(catalogo, numero_os=100_000_000_000))

        assert resposta.status_code == 422
        assert 'VLD-001' in _codigos_do_campo(resposta.json()['erros'], 'numero_os')
        assert Rad.objects.count() == 0

    def test_os_de_11_digitos_sincroniza_tambem_com_a_os_opcional(self, client, catalogo, usuario_com_token):
        _tornar_os_opcional()
        _, token = usuario_com_token
        resposta = _sincronizar(
            client, token, _payload(catalogo, numero_os=OS_REAL_DE_11_DIGITOS)
        )
        assert resposta.status_code == 201, resposta.content


# ---------------------------------------------------------------------------
# Validacao da OS
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestValidacaoDaOs:
    def test_limite_configurado_e_11_digitos(self):
        assert LIMITE_DIGITOS_OS == 11

    def test_os_com_exatamente_11_digitos_e_valida(self, catalogo):
        assert _codigos_do_campo(_validar(_payload(catalogo, numero_os=99_999_999_999)), 'numero_os') == []

    def test_os_com_7_digitos_continua_valida(self, catalogo):
        assert _codigos_do_campo(_validar(_payload(catalogo, numero_os=9_999_999)), 'numero_os') == []

    @pytest.mark.parametrize('valor', [0, -5, None, 'abc'])
    def test_os_invalida_e_recusada(self, catalogo, valor):
        assert _codigos_do_campo(_validar(_payload(catalogo, numero_os=valor)), 'numero_os') == ['VLD-001']


# ---------------------------------------------------------------------------
# "Opcional" libera o campo em BRANCO, nunca o formato
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCampoOpcionalNaoApagaValidacaoDeFormato:
    def test_os_opcional_e_em_branco_nao_gera_erro_de_os(self, catalogo):
        _tornar_os_opcional()
        assert _codigos_do_campo(_validar(_payload(catalogo, numero_os=None)), 'numero_os') == []

    def test_os_opcional_mas_preenchida_grande_demais_continua_com_erro(self, catalogo):
        _tornar_os_opcional()
        erros = _validar(_payload(catalogo, numero_os=100_000_000_000))
        assert _codigos_do_campo(erros, 'numero_os') == ['VLD-001']

    def test_os_obrigatoria_e_em_branco_continua_com_erro(self, catalogo):
        CampoFormulario.objects.update_or_create(
            chave='numero_os', defaults={'rotulo': 'OS', 'habilitado': True, 'obrigatorio': True}
        )
        assert _codigos_do_campo(_validar(_payload(catalogo, numero_os=None)), 'numero_os') == ['VLD-001']

    def test_responsavel_atividade_opcional_mas_acima_de_50_caracteres_continua_com_erro(self, catalogo):
        """Mesma regra, em outro campo: opcional nao libera o limite de tamanho."""
        CampoFormulario.objects.update_or_create(
            chave='responsavel_atividade',
            defaults={'rotulo': 'Responsavel Atividade', 'habilitado': True, 'obrigatorio': False},
        )
        erros = _validar(_payload(catalogo, responsavel_atividade='x' * 51))
        assert _codigos_do_campo(erros, 'responsavel_atividade') == ['VLD-029']

    def test_responsavel_atividade_opcional_e_em_branco_nao_gera_erro(self, catalogo):
        CampoFormulario.objects.update_or_create(
            chave='responsavel_atividade',
            defaults={'rotulo': 'Responsavel Atividade', 'habilitado': True, 'obrigatorio': False},
        )
        erros = _validar(_payload(catalogo, responsavel_atividade=''))
        assert _codigos_do_campo(erros, 'responsavel_atividade') == []


# ---------------------------------------------------------------------------
# Trava de numeracao por OS
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTravaDeNumeracaoPorOs:
    @pytest.mark.parametrize('os_numero', [1, 4321, 2_147_483_647, 2_147_483_648, OS_REAL_DE_11_DIGITOS, 99_999_999_999])
    def test_gerar_numero_execucao_aceita_qualquer_tamanho_de_os(self, os_numero):
        assert gerar_numero_execucao(os_numero) == 1
