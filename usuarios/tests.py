"""
Testes do app usuarios.

Cobre os cenarios do PLANO_DE_TESTES.docx, modulo AUTH, que sao
testaveis no backend (Django). Cenarios que dependem de comportamento
client-side/offline (IndexedDB, Service Worker) — AUTH-003, AUTH-005,
AUTH-006, AUTH-007, AUTH-008 — pertencem ao frontend e devem ser
cobertos por testes de JS/E2E quando essa camada for implementada.
"""
import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Token, Usuario, UsuarioPerfil


@pytest.mark.django_db
class TestLogin:
    def test_auth_001_login_valido_gera_token(self, client):
        """AUTH-001: login valido com conexao -> token de 7 dias gerado."""
        usuario = Usuario.objects.create(login='joao.silva')

        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'joao.silva'}),
            content_type='application/json',
        )

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['login'] == 'joao.silva'
        assert Token.objects.filter(usuario=usuario).count() == 1

        token = Token.objects.get(usuario=usuario)
        segundos_validade = (token.validade - token.data_criacao).total_seconds()
        # Tolerancia de poucos segundos entre as duas chamadas a timezone.now()
        assert abs(segundos_validade - timedelta(days=7).total_seconds()) < 5

    def test_auth_002_login_inexistente_e_recusado(self, client):
        """AUTH-002: login nao cadastrado -> recusado, nenhum token gerado."""
        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'nao.existe'}),
            content_type='application/json',
        )

        assert resposta.status_code == 401
        assert Token.objects.count() == 0

    def test_login_usuario_inativo_e_recusado(self, client):
        """Usuario inativo nao consegue fazer login (RG conforme tabela usuarios.ativo)."""
        Usuario.objects.create(login='ex.funcionario', ativo=False)

        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'ex.funcionario'}),
            content_type='application/json',
        )

        assert resposta.status_code == 401
        assert Token.objects.count() == 0

    def test_login_sem_informar_login_retorna_erro(self, client):
        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({}),
            content_type='application/json',
        )
        assert resposta.status_code == 400

    def test_login_corpo_json_invalido_retorna_400(self, client):
        resposta = client.post(
            reverse('usuarios:login'),
            data='isto-nao-e-json-valido{{{',
            content_type='application/json',
        )
        assert resposta.status_code == 400

    def test_login_com_login_repetido_reutiliza_mesmo_usuario(self, client):
        """O sistema permite multiplos logins/tokens para o mesmo usuario (multi-dispositivo)."""
        Usuario.objects.create(login='maria.souza')

        client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'maria.souza', 'dispositivo': 'celular'}),
            content_type='application/json',
        )
        client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'maria.souza', 'dispositivo': 'computador'}),
            content_type='application/json',
        )

        assert Token.objects.filter(usuario__login='maria.souza').count() == 2


@pytest.mark.django_db
class TestValidarToken:
    def test_auth_004_token_expirado_e_recusado(self, client):
        """AUTH-004: token expirado -> login recusado com mensagem especifica."""
        usuario = Usuario.objects.create(login='pedro.lima')
        token = Token.objects.create(
            usuario=usuario,
            token='token-expirado-teste',
            validade=timezone.now() - timedelta(days=1),
        )

        resposta = client.get(
            reverse('usuarios:validar_token'),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.status_code == 401
        assert 'expirou' in resposta.json()['erro'].lower()

    def test_token_valido_retorna_perfis_do_usuario(self, client):
        usuario = Usuario.objects.create(login='ana.costa')
        UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.SUPERVISOR)
        token = Token.gerar_para(usuario)

        resposta = client.get(
            reverse('usuarios:validar_token'),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.status_code == 200
        assert resposta.json()['perfis'] == ['supervisor']

    def test_token_ausente_retorna_401(self, client):
        resposta = client.get(reverse('usuarios:validar_token'))
        assert resposta.status_code == 401

    def test_token_invalido_retorna_401(self, client):
        resposta = client.get(
            reverse('usuarios:validar_token'),
            HTTP_AUTHORIZATION='Token nao-existe',
        )
        assert resposta.status_code == 401

    def test_usuario_desativado_apos_emissao_do_token_e_recusado(self, client):
        """
        Cenario distinto de login com usuario inativo (que bloqueia a
        EMISSAO de um token novo): aqui o usuario tinha um token valido
        e nao expirado, mas foi desativado DEPOIS -- por exemplo, um
        Administrador revogando o acesso de alguem que ja estava
        logado. O token continua tecnicamente valido/nao expirado, mas
        o acesso precisa ser recusado mesmo assim.
        """
        usuario = Usuario.objects.create(login='revogado.durante.sessao')
        token = Token.gerar_para(usuario)

        usuario.ativo = False
        usuario.save()

        resposta = client.get(
            reverse('usuarios:validar_token'),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 403


@pytest.mark.django_db
class TestPerfis:
    def test_usuario_pode_ter_dois_perfis_simultaneos(self):
        """PRM-025: um login pode ter ate 2 perfis ativos simultaneamente."""
        usuario = Usuario.objects.create(login='carlos.dual')
        UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.USUARIO)
        UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.SUPERVISOR)

        assert set(usuario.lista_perfis) == {'usuario', 'supervisor'}

    def test_nao_permite_perfil_duplicado_para_mesmo_usuario(self):
        """Combinacao id_usuario + perfil deve ser unica (Modelo Logico 6.2)."""
        from django.db import IntegrityError

        usuario = Usuario.objects.create(login='duplicado.teste')
        UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.USUARIO)

        with pytest.raises(IntegrityError):
            UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.USUARIO)
