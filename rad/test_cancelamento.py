"""
Testes do endpoint POST /rad/<numero_rad>/cancelar/ — RG-CAN-001 a 012.
"""
import json

import pytest
from django.urls import reverse

from rad.models import Rad
from usuarios.models import Token, Usuario, UsuarioPerfil

from .test_views import _payload_valido, catalogo_basico  # reaproveita fixtures


@pytest.fixture
def administrador_com_token(db):
    usuario = Usuario.objects.create(login='admin.cancelamento')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.ADMINISTRADOR)
    token = Token.gerar_para(usuario)
    return usuario, token


@pytest.fixture
def usuario_comum_com_token(db):
    usuario = Usuario.objects.create(login='tecnico.sem.permissao')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.USUARIO)
    token = Token.gerar_para(usuario)
    return usuario, token


def _criar_rad_sincronizado(client, token, catalogo_basico, sync_id):
    resposta = client.post(
        reverse('rad:sincronizar'),
        data=json.dumps(_payload_valido(catalogo_basico, sync_id_tentativa=sync_id)),
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Token {token.token}',
    )
    assert resposta.status_code == 201
    return resposta.json()['numero_rad']


@pytest.mark.django_db
class TestCancelarRad:
    def test_administrador_cancela_com_sucesso(
        self, client, administrador_com_token, catalogo_basico
    ):
        admin, token_admin = administrador_com_token
        # RAD precisa ser criado por algum usuario tecnico primeiro
        tecnico = Usuario.objects.create(login='tec.cria.rad')
        token_tecnico = Token.gerar_para(tecnico)
        numero_rad = _criar_rad_sincronizado(
            client, token_tecnico, catalogo_basico, 'cancelamento-ok'
        )

        resposta = client.post(
            reverse('rad:cancelar', args=[numero_rad]),
            data=json.dumps({'justificativa': 'SA duplicada por engano.'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )

        assert resposta.status_code == 200
        assert resposta.json()['status'] == 'cancelado'

        rad = Rad.objects.get(numero_rad=numero_rad)
        assert rad.status == Rad.CANCELADO
        assert rad.justificativa_cancelamento == 'SA duplicada por engano.'
        assert rad.usuario_cancelamento == admin
        assert rad.data_cancelamento is not None

    def test_rg_can_002_usuario_comum_nao_pode_cancelar(
        self, client, usuario_comum_com_token, catalogo_basico
    ):
        _, token = usuario_comum_com_token
        numero_rad = _criar_rad_sincronizado(client, token, catalogo_basico, 'sem-permissao')

        resposta = client.post(
            reverse('rad:cancelar', args=[numero_rad]),
            data=json.dumps({'justificativa': 'Tentativa indevida.'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.status_code == 403
        assert Rad.objects.get(numero_rad=numero_rad).status == Rad.SINCRONIZADO

    def test_rg_can_005_justificativa_obrigatoria(
        self, client, administrador_com_token, catalogo_basico
    ):
        _, token_admin = administrador_com_token
        tecnico = Usuario.objects.create(login='tec.just')
        token_tecnico = Token.gerar_para(tecnico)
        numero_rad = _criar_rad_sincronizado(
            client, token_tecnico, catalogo_basico, 'sem-justificativa'
        )

        resposta = client.post(
            reverse('rad:cancelar', args=[numero_rad]),
            data=json.dumps({'justificativa': ''}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )

        assert resposta.status_code == 422
        assert Rad.objects.get(numero_rad=numero_rad).status == Rad.SINCRONIZADO

    def test_rg_can_009_cancelamento_e_irreversivel(
        self, client, administrador_com_token, catalogo_basico
    ):
        _, token_admin = administrador_com_token
        tecnico = Usuario.objects.create(login='tec.irrev')
        token_tecnico = Token.gerar_para(tecnico)
        numero_rad = _criar_rad_sincronizado(
            client, token_tecnico, catalogo_basico, 'irreversivel'
        )

        primeira = client.post(
            reverse('rad:cancelar', args=[numero_rad]),
            data=json.dumps({'justificativa': 'Primeiro cancelamento.'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )
        segunda = client.post(
            reverse('rad:cancelar', args=[numero_rad]),
            data=json.dumps({'justificativa': 'Tentando cancelar de novo.'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )

        assert primeira.status_code == 200
        assert segunda.status_code == 409

    def test_rg_can_011_numero_execucao_preservado_apos_cancelamento(
        self, client, administrador_com_token, catalogo_basico
    ):
        _, token_admin = administrador_com_token
        tecnico = Usuario.objects.create(login='tec.exec')
        token_tecnico = Token.gerar_para(tecnico)
        numero_rad = _criar_rad_sincronizado(
            client, token_tecnico, catalogo_basico, 'preserva-execucao'
        )
        numero_execucao_antes = Rad.objects.get(numero_rad=numero_rad).numero_execucao

        client.post(
            reverse('rad:cancelar', args=[numero_rad]),
            data=json.dumps({'justificativa': 'Motivo qualquer.'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )

        rad = Rad.objects.get(numero_rad=numero_rad)
        assert rad.numero_execucao == numero_execucao_antes

    def test_corpo_da_requisicao_invalido_retorna_400(
        self, client, administrador_com_token, catalogo_basico
    ):
        _, token_admin = administrador_com_token
        tecnico = Usuario.objects.create(login='tec.json.invalido')
        token_tecnico = Token.gerar_para(tecnico)
        numero_rad = _criar_rad_sincronizado(
            client, token_tecnico, catalogo_basico, 'cancelar-json-invalido'
        )

        resposta = client.post(
            reverse('rad:cancelar', args=[numero_rad]),
            data='isto-nao-e-json-valido{{{',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )
        assert resposta.status_code == 400

    def test_rad_inexistente_retorna_404(self, client, administrador_com_token):
        _, token_admin = administrador_com_token
        resposta = client.post(
            reverse('rad:cancelar', args=['R99999']),
            data=json.dumps({'justificativa': 'Motivo qualquer.'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )
        assert resposta.status_code == 404
