"""
Testes do app configuracoes — habilitar/desabilitar campos do
formulario (mudanca de negocio 17/07/2026).
"""
import pytest
from django.urls import reverse

from configuracoes.models import CampoFormulario
from configuracoes.servicos import campos_desabilitados
from usuarios.models import Token, Usuario, UsuarioPerfil


@pytest.fixture
def administrador_com_token(db):
    usuario = Usuario.objects.create(login='admin.config')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.ADMINISTRADOR)
    return usuario, Token.gerar_para(usuario)


@pytest.fixture
def supervisor_com_token(db):
    usuario = Usuario.objects.create(login='supervisor.config')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.SUPERVISOR)
    return usuario, Token.gerar_para(usuario)


@pytest.fixture
def campo_teste(db):
    return CampoFormulario.objects.create(chave='campo_teste', rotulo='Campo de Teste')


@pytest.mark.django_db
class TestListarCampos:
    def test_qualquer_usuario_autenticado_pode_listar(self, client, campo_teste):
        usuario = Usuario.objects.create(login='qualquer.usuario')
        token = Token.gerar_para(usuario)

        resposta = client.get(
            reverse('configuracoes:listar_campos'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        assert resposta.status_code == 200
        chaves = [c['chave'] for c in resposta.json()['campos']]
        assert 'campo_teste' in chaves

    def test_migracao_de_dados_populou_todos_os_31_campos(self):
        """Migration 0002_popular_campos_formulario deve ter criado os campos do RAD."""
        assert CampoFormulario.objects.filter(
            chave__in=['numero_os', 'responsavel_atividade', 'equipes', 'amv']
        ).count() == 4


@pytest.mark.django_db
class TestDesabilitarEHabilitar:
    def test_administrador_desabilita_campo(self, client, administrador_com_token, campo_teste):
        _, token = administrador_com_token
        resposta = client.post(
            reverse('configuracoes:desabilitar_campo', args=['campo_teste']),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 200
        campo_teste.refresh_from_db()
        assert campo_teste.habilitado is False
        assert campo_teste.atualizado_por is not None

    def test_administrador_reabilita_campo(self, client, administrador_com_token, campo_teste):
        _, token = administrador_com_token
        campo_teste.habilitado = False
        campo_teste.save()

        resposta = client.post(
            reverse('configuracoes:habilitar_campo', args=['campo_teste']),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 200
        campo_teste.refresh_from_db()
        assert campo_teste.habilitado is True

    def test_supervisor_nao_pode_desabilitar(self, client, supervisor_com_token, campo_teste):
        _, token = supervisor_com_token
        resposta = client.post(
            reverse('configuracoes:desabilitar_campo', args=['campo_teste']),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 403
        campo_teste.refresh_from_db()
        assert campo_teste.habilitado is True

    def test_desabilitar_campo_inexistente_retorna_404(self, client, administrador_com_token):
        _, token = administrador_com_token
        resposta = client.post(
            reverse('configuracoes:desabilitar_campo', args=['nao_existe']),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 404


@pytest.mark.django_db
class TestCamposDesabilitados:
    def test_campos_desabilitados_retorna_apenas_desabilitados(self, campo_teste):
        outro = CampoFormulario.objects.create(chave='outro_campo', rotulo='Outro')
        campo_teste.habilitado = False
        campo_teste.save()

        assert campos_desabilitados() == {'campo_teste'}
        assert 'outro_campo' not in campos_desabilitados()
