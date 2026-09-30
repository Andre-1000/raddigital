"""
Testes do app usuarios.

Cobre os cenarios do PLANO_DE_TESTES.docx, modulo AUTH, que sao
testaveis no backend (Django). Cenarios que dependem de comportamento
client-side/offline (IndexedDB, Service Worker) — AUTH-003, AUTH-005,
AUTH-006, AUTH-007, AUTH-008 — pertencem ao frontend e devem ser
cobertos por testes de JS/E2E quando essa camada for implementada.

28/09/2026: TestLogin reescrita -- estava desatualizada desde
30/07/2026 (fazia login sem enviar senha, de antes do login exigir
senha de verdade). Reescrita tambem incorpora a mudanca de 28/09/2026
(login so aceita matricula, nao mais e-mail).
"""
import json
from datetime import timedelta

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Token, Usuario, UsuarioPerfil

SENHA_VALIDA_TESTE = 'S3nhaForte!2026'


def _criar_usuario_com_senha(login, senha=SENHA_VALIDA_TESTE, **kwargs):
    """
    28/09/2026: helper usado por quase todo teste de login daqui pra
    frente -- o login() atual exige senha_hash preenchido (usuario
    "legado" sem senha recebe 401 com senha_nao_definida=True, nunca
    200), entao criar o Usuario sozinho (como os testes antigos
    faziam) nao basta mais.
    """
    usuario = Usuario.objects.create(login=login, **kwargs)
    usuario.definir_senha(senha)
    usuario.save(update_fields=['senha_hash'])
    return usuario


@pytest.mark.django_db
class TestLogin:
    def test_auth_001_login_valido_gera_token(self, client):
        """AUTH-001: login (matricula) + senha corretos, com conexao -> token de 7 dias gerado."""
        usuario = _criar_usuario_com_senha('joao.silva')

        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'joao.silva', 'senha': SENHA_VALIDA_TESTE}),
            content_type='application/json',
        )

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['login'] == 'joao.silva'
        assert 'token' in corpo  # valor em texto puro, so existe nesta resposta (ver Token.gerar_para)
        assert Token.objects.filter(usuario=usuario).count() == 1

        token = Token.objects.get(usuario=usuario)
        segundos_validade = (token.validade - token.data_criacao).total_seconds()
        # Tolerancia de poucos segundos entre as duas chamadas a timezone.now()
        assert abs(segundos_validade - timedelta(days=7).total_seconds()) < 5

    def test_auth_002_login_inexistente_e_recusado(self, client):
        """AUTH-002: login nao cadastrado -> recusado, nenhum token gerado."""
        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'nao.existe', 'senha': 'qualquer-coisa'}),
            content_type='application/json',
        )

        assert resposta.status_code == 401
        assert Token.objects.count() == 0

    def test_login_usuario_inativo_e_recusado(self, client):
        """Usuario inativo nao consegue fazer login (RG conforme tabela usuarios.ativo)."""
        _criar_usuario_com_senha('ex.funcionario', ativo=False)

        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'ex.funcionario', 'senha': SENHA_VALIDA_TESTE}),
            content_type='application/json',
        )

        assert resposta.status_code == 401
        assert Token.objects.count() == 0

    def test_login_sem_informar_login_retorna_erro(self, client):
        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'senha': SENHA_VALIDA_TESTE}),
            content_type='application/json',
        )
        assert resposta.status_code == 400

    def test_login_sem_informar_senha_retorna_erro(self, client):
        """28/09/2026: caso irmao do teste acima -- login presente, senha ausente."""
        _criar_usuario_com_senha('sem.senha.no.post')

        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'sem.senha.no.post'}),
            content_type='application/json',
        )
        assert resposta.status_code == 400
        assert Token.objects.count() == 0

    def test_login_corpo_json_invalido_retorna_400(self, client):
        resposta = client.post(
            reverse('usuarios:login'),
            data='isto-nao-e-json-valido{{{',
            content_type='application/json',
        )
        assert resposta.status_code == 400

    def test_login_com_login_repetido_reutiliza_mesmo_usuario(self, client):
        """O sistema permite multiplos logins/tokens para o mesmo usuario (multi-dispositivo)."""
        _criar_usuario_com_senha('maria.souza')

        client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'maria.souza', 'senha': SENHA_VALIDA_TESTE, 'dispositivo': 'celular'}),
            content_type='application/json',
        )
        client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'maria.souza', 'senha': SENHA_VALIDA_TESTE, 'dispositivo': 'computador'}),
            content_type='application/json',
        )

        assert Token.objects.filter(usuario__login='maria.souza').count() == 2

    def test_login_com_senha_incorreta_e_recusado(self, client):
        """30/07/2026: senha errada -> 401, mensagem generica (nao revela se o login existe)."""
        _criar_usuario_com_senha('carlos.senha')

        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'carlos.senha', 'senha': 'senha-errada-123'}),
            content_type='application/json',
        )

        assert resposta.status_code == 401
        assert Token.objects.count() == 0

    def test_login_usuario_sem_senha_definida_orienta_esqueci_senha(self, client):
        """
        30/07/2026: usuario 'legado' (senha_hash vazio) recebe erro
        especifico com senha_nao_definida=True -- o frontend usa essa
        flag pra apontar direto pro fluxo de "Esqueci minha senha".
        """
        Usuario.objects.create(login='legado.sem.senha')  # sem definir_senha() de proposito

        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'legado.sem.senha', 'senha': 'qualquer-coisa'}),
            content_type='application/json',
        )

        assert resposta.status_code == 401
        assert resposta.json().get('senha_nao_definida') is True

    def test_login_bloqueia_apos_tentativas_maximas(self, client):
        """
        30/07/2026: rate limit contra forca bruta -- apos
        MAXIMO_TENTATIVAS_LOGIN erros seguidos, ate a senha CORRETA
        passa a ser recusada (429) durante o periodo de bloqueio.
        """
        _criar_usuario_com_senha('bloqueio.teste')
        maximo = getattr(settings, 'MAXIMO_TENTATIVAS_LOGIN', 5)

        for _ in range(maximo):
            resposta_errada = client.post(
                reverse('usuarios:login'),
                data=json.dumps({'login': 'bloqueio.teste', 'senha': 'senha-errada'}),
                content_type='application/json',
            )
            assert resposta_errada.status_code == 401

        resposta_certa = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'bloqueio.teste', 'senha': SENHA_VALIDA_TESTE}),
            content_type='application/json',
        )
        assert resposta_certa.status_code == 429
        assert Token.objects.count() == 0

    def test_login_com_email_nao_funciona_mais(self, client):
        """
        28/09/2026: login deixou de aceitar e-mail -- digitar o e-mail
        cadastrado no campo 'login' precisa ser recusado, mesmo com a
        senha correta. O e-mail continua existindo no cadastro, so
        nao serve mais pra entrar (fica exclusivo de "Esqueci minha
        senha").
        """
        _criar_usuario_com_senha('rita.alves', email='rita.alves@example.com')

        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'rita.alves@example.com', 'senha': SENHA_VALIDA_TESTE}),
            content_type='application/json',
        )

        assert resposta.status_code == 401
        assert Token.objects.count() == 0


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
