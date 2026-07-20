"""
Testes do app colaboradores — RG-RESP-002, 003, 008, 011, 012.
"""
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from colaboradores.models import ColaboradorCadastro
from usuarios.models import Token, Usuario, UsuarioPerfil


@pytest.fixture
def administrador_com_token(db):
    usuario = Usuario.objects.create(login='admin.colab')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.ADMINISTRADOR)
    return usuario, Token.gerar_para(usuario)


@pytest.fixture
def usuario_comum_com_token(db):
    usuario = Usuario.objects.create(login='comum.colab')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.USUARIO)
    return usuario, Token.gerar_para(usuario)


@pytest.fixture
def supervisor_com_token(db):
    usuario = Usuario.objects.create(login='supervisor.colab')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.SUPERVISOR)
    return usuario, Token.gerar_para(usuario)


@pytest.mark.django_db
class TestCriar:
    def test_administrador_cria_colaborador(self, client, administrador_com_token):
        _, token = administrador_com_token
        resposta = client.post(
            reverse('colaboradores:criar'),
            data=json.dumps({'registro_empresa': '12345', 'nome': 'Fulano de Tal'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 201
        assert ColaboradorCadastro.objects.filter(registro_empresa='12345').exists()

    def test_rg_resp_012_usuario_comum_nao_pode_criar(
        self, client, usuario_comum_com_token
    ):
        _, token = usuario_comum_com_token
        resposta = client.post(
            reverse('colaboradores:criar'),
            data=json.dumps({'registro_empresa': '99999', 'nome': 'Tentativa Indevida'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 403
        assert not ColaboradorCadastro.objects.filter(registro_empresa='99999').exists()

    def test_rg_resp_002_registro_deve_ser_numerico(
        self, client, administrador_com_token
    ):
        _, token = administrador_com_token
        resposta = client.post(
            reverse('colaboradores:criar'),
            data=json.dumps({'registro_empresa': 'ABC123', 'nome': 'Invalido'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 422

    def test_registro_duplicado_e_rejeitado(self, client, administrador_com_token):
        _, token = administrador_com_token
        ColaboradorCadastro.objects.create(registro_empresa='55555', nome='Ja Existe')
        resposta = client.post(
            reverse('colaboradores:criar'),
            data=json.dumps({'registro_empresa': '55555', 'nome': 'Outro Nome'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 422


@pytest.mark.django_db
class TestBuscar:
    def test_busca_por_registro(self, client, usuario_comum_com_token):
        _, token = usuario_comum_com_token
        ColaboradorCadastro.objects.create(registro_empresa='11111', nome='Joao Silva')

        resposta = client.get(
            reverse('colaboradores:buscar'), {'q': '11111'},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 200
        assert len(resposta.json()['resultados']) == 1

    def test_busca_por_nome(self, client, usuario_comum_com_token):
        _, token = usuario_comum_com_token
        ColaboradorCadastro.objects.create(registro_empresa='22222', nome='Maria Souza')

        resposta = client.get(
            reverse('colaboradores:buscar'), {'q': 'Maria'},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert len(resposta.json()['resultados']) == 1

    def test_busca_nao_retorna_inativos(self, client, usuario_comum_com_token):
        _, token = usuario_comum_com_token
        ColaboradorCadastro.objects.create(
            registro_empresa='33333', nome='Ex Funcionario', ativo=False
        )

        resposta = client.get(
            reverse('colaboradores:buscar'), {'q': '33333'},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.json()['resultados'] == []

    def test_rg_resp_008_nao_localizado_retorna_lista_vazia(
        self, client, usuario_comum_com_token
    ):
        _, token = usuario_comum_com_token
        resposta = client.get(
            reverse('colaboradores:buscar'), {'q': 'nao existe ninguem assim'},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.json()['resultados'] == []


@pytest.mark.django_db
class TestEditarEExcluir:
    def test_administrador_edita_colaborador(self, client, administrador_com_token):
        _, token = administrador_com_token
        colaborador = ColaboradorCadastro.objects.create(
            registro_empresa='44444', nome='Nome Antigo'
        )

        resposta = client.post(
            reverse('colaboradores:editar', args=[colaborador.id]),
            data=json.dumps({'nome': 'Nome Novo'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.status_code == 200
        colaborador.refresh_from_db()
        assert colaborador.nome == 'Nome Novo'

    def test_rg_resp_011_editar_nao_afeta_rad_ja_sincronizado(
        self, client, administrador_com_token
    ):
        """
        rad_colaboradores e uma copia independente (RadColaborador),
        entao editar o cadastro oficial nao deve alterar RADs existentes
        -- garantido estruturalmente porque RadColaborador nao tem FK
        para ColaboradorCadastro, apenas uma copia de nome/registro.
        """
        from rad.models import RadColaborador

        assert 'colaborador_cadastro' not in [
            f.name for f in RadColaborador._meta.get_fields()
        ]

    def test_administrador_exclui_colaborador(self, client, administrador_com_token):
        _, token = administrador_com_token
        colaborador = ColaboradorCadastro.objects.create(
            registro_empresa='66666', nome='Sera Excluido'
        )

        resposta = client.post(
            reverse('colaboradores:excluir', args=[colaborador.id]),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.status_code == 200
        assert not ColaboradorCadastro.objects.filter(id=colaborador.id).exists()

    def test_usuario_comum_nao_pode_excluir(self, client, usuario_comum_com_token):
        _, token = usuario_comum_com_token
        colaborador = ColaboradorCadastro.objects.create(
            registro_empresa='77777', nome='Protegido'
        )

        resposta = client.post(
            reverse('colaboradores:excluir', args=[colaborador.id]),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.status_code == 403
        assert ColaboradorCadastro.objects.filter(id=colaborador.id).exists()


@pytest.mark.django_db
class TestListarTodos:
    """GET /colaboradores/todos/ — cache offline (RadDB) para adicionar colaboradores sem conexao."""

    def test_requer_token(self, client):
        resposta = client.get(reverse('colaboradores:listar_todos'))
        assert resposta.status_code == 401

    def test_retorna_apenas_ativos(self, client, usuario_comum_com_token):
        _, token = usuario_comum_com_token
        ColaboradorCadastro.objects.create(registro_empresa='11111', nome='Ativo', ativo=True)
        ColaboradorCadastro.objects.create(registro_empresa='22222', nome='Inativo', ativo=False)

        resposta = client.get(
            reverse('colaboradores:listar_todos'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        assert resposta.status_code == 200
        nomes = [c['nome'] for c in resposta.json()['colaboradores']]
        assert 'Ativo' in nomes
        assert 'Inativo' not in nomes

    def test_formato_dos_itens(self, client, usuario_comum_com_token):
        _, token = usuario_comum_com_token
        ColaboradorCadastro.objects.create(registro_empresa='33333', nome='Fulano')

        resposta = client.get(
            reverse('colaboradores:listar_todos'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        item = resposta.json()['colaboradores'][0]
        assert set(item.keys()) == {'registro_empresa', 'nome'}


@pytest.mark.django_db
class TestListarParaAdministrar:
    """GET /colaboradores/administrar/ — inclui inativos, exclusivo do Administrador."""

    def test_requer_token(self, client):
        resposta = client.get(reverse('colaboradores:listar_para_administrar'))
        assert resposta.status_code == 401

    def test_usuario_comum_nao_pode_acessar(self, client, usuario_comum_com_token):
        _, token = usuario_comum_com_token
        resposta = client.get(
            reverse('colaboradores:listar_para_administrar'),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 403

    def test_supervisor_nao_pode_acessar(self, client, supervisor_com_token):
        _, token = supervisor_com_token
        resposta = client.get(
            reverse('colaboradores:listar_para_administrar'),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 403

    def test_administrador_ve_ativos_e_inativos(self, client, administrador_com_token):
        _, token = administrador_com_token
        ColaboradorCadastro.objects.create(registro_empresa='11111', nome='Ativo', ativo=True)
        ColaboradorCadastro.objects.create(registro_empresa='22222', nome='Inativo', ativo=False)

        resposta = client.get(
            reverse('colaboradores:listar_para_administrar'),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 200
        nomes = {c['nome'] for c in resposta.json()['colaboradores']}
        assert nomes == {'Ativo', 'Inativo'}

    def test_formato_completo_dos_itens(self, client, administrador_com_token):
        _, token = administrador_com_token
        ColaboradorCadastro.objects.create(registro_empresa='44444', nome='Completo')

        resposta = client.get(
            reverse('colaboradores:listar_para_administrar'),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        item = resposta.json()['colaboradores'][0]
        assert set(item.keys()) == {'id', 'registro_empresa', 'nome', 'ativo'}


@pytest.mark.django_db
class TestImportarCsv:
    """POST /colaboradores/importar/ — importacao em lote (RG-RESP-012)."""

    def _enviar_csv(self, client, token, conteudo_bytes, nome_arquivo='lista.csv'):
        arquivo = SimpleUploadedFile(nome_arquivo, conteudo_bytes, content_type='text/csv')
        return client.post(
            reverse('colaboradores:importar'),
            data={'arquivo': arquivo},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

    def test_requer_token(self, client):
        resposta = client.post(reverse('colaboradores:importar'))
        assert resposta.status_code == 401

    def test_usuario_comum_nao_pode_importar(self, client, usuario_comum_com_token):
        _, token = usuario_comum_com_token
        resposta = self._enviar_csv(client, token, b'12345,Fulano de Tal\n')
        assert resposta.status_code == 403

    def test_importa_csv_com_virgula_sem_cabecalho(self, client, administrador_com_token):
        _, token = administrador_com_token
        conteudo = b'12345,Fulano de Tal\n67890,Ciclana Souza\n'

        resposta = self._enviar_csv(client, token, conteudo)

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['criados'] == 2
        assert corpo['atualizados'] == 0
        assert corpo['erros'] == []
        assert ColaboradorCadastro.objects.filter(registro_empresa='12345', nome='Fulano de Tal').exists()
        assert ColaboradorCadastro.objects.filter(registro_empresa='67890', nome='Ciclana Souza').exists()

    def test_importa_csv_com_ponto_e_virgula_excel_br(self, client, administrador_com_token):
        """Excel em portugues do Brasil costuma exportar CSV com ; em vez de ,"""
        _, token = administrador_com_token
        conteudo = 'Registro;Nome\n11111;João da Silva\n22222;Márcia Aparecida\n'.encode('utf-8-sig')

        resposta = self._enviar_csv(client, token, conteudo)

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['criados'] == 2
        assert ColaboradorCadastro.objects.get(registro_empresa='11111').nome == 'João da Silva'
        assert ColaboradorCadastro.objects.get(registro_empresa='22222').nome == 'Márcia Aparecida'

    def test_deteccao_de_cabecalho_e_case_insensitive_ao_conteudo(self, client, administrador_com_token):
        """Linha de cabecalho (primeira coluna nao numerica) e ignorada, nao vira erro."""
        _, token = administrador_com_token
        conteudo = b'registro_empresa,nome\n12345,Fulano\n'

        resposta = self._enviar_csv(client, token, conteudo)

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['criados'] == 1
        assert corpo['erros'] == []

    def test_upsert_atualiza_quem_ja_existe_e_reativa(self, client, administrador_com_token):
        """
        Rodar a importacao de novo com uma lista atualizada nao deve
        duplicar nem falhar -- deve atualizar o nome e reativar quem
        estava desativado.
        """
        _, token = administrador_com_token
        ColaboradorCadastro.objects.create(
            registro_empresa='12345', nome='Nome Antigo', ativo=False
        )

        resposta = self._enviar_csv(client, token, b'12345,Nome Atualizado\n')

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['criados'] == 0
        assert corpo['atualizados'] == 1
        colaborador = ColaboradorCadastro.objects.get(registro_empresa='12345')
        assert colaborador.nome == 'Nome Atualizado'
        assert colaborador.ativo is True

    def test_linha_com_registro_invalido_e_reportada_sem_travar_o_resto(self, client, administrador_com_token):
        _, token = administrador_com_token
        conteudo = b'12345,Fulano Valido\nABC123,Registro Invalido\n67890,Outro Valido\n'

        resposta = self._enviar_csv(client, token, conteudo)

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['criados'] == 2
        assert len(corpo['erros']) == 1
        assert corpo['erros'][0]['linha'] == 2
        assert ColaboradorCadastro.objects.filter(registro_empresa='12345').exists()
        assert ColaboradorCadastro.objects.filter(registro_empresa='67890').exists()

    def test_linha_sem_nome_e_reportada(self, client, administrador_com_token):
        _, token = administrador_com_token
        resposta = self._enviar_csv(client, token, b'12345,\n')

        corpo = resposta.json()
        assert corpo['criados'] == 0
        assert len(corpo['erros']) == 1
        assert 'nome' in corpo['erros'][0]['mensagem'].lower()

    def test_sem_arquivo_retorna_400(self, client, administrador_com_token):
        _, token = administrador_com_token
        resposta = client.post(
            reverse('colaboradores:importar'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        assert resposta.status_code == 400

    def test_arquivo_vazio_retorna_400(self, client, administrador_com_token):
        _, token = administrador_com_token
        resposta = self._enviar_csv(client, token, b'')
        assert resposta.status_code == 400

    def test_arquivo_binario_incompreensivel_nao_derruba_a_importacao(self, client, administrador_com_token):
        """
        Latin-1 (o ultimo fallback de codificacao) decodifica QUALQUER
        sequencia de bytes -- entao um arquivo binario de verdade (uma
        imagem, por exemplo) nao gera erro 400 de leitura, e sim "texto"
        sem sentido que falha na validacao linha a linha. O importante
        e que isso nao derruba a requisicao com um erro 500.
        """
        _, token = administrador_com_token
        conteudo_binario = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46])
        resposta = self._enviar_csv(client, token, conteudo_binario, nome_arquivo='invalido.csv')
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['criados'] == 0

    def test_arquivo_grande_demais_e_recusado(self, client, administrador_com_token):
        _, token = administrador_com_token
        conteudo_grande = b'12345,Fulano\n' * 500_000  # bem acima de 5MB
        resposta = self._enviar_csv(client, token, conteudo_grande)
        assert resposta.status_code == 400

    def test_importacao_grande_funciona(self, client, administrador_com_token):
        """A CPTM mencionou que a lista real e grande -- confirma que centenas de linhas funcionam."""
        _, token = administrador_com_token
        linhas = [f'{100000 + i},Colaborador Numero {i}' for i in range(500)]
        conteudo = ('\n'.join(linhas) + '\n').encode('utf-8')

        resposta = self._enviar_csv(client, token, conteudo)

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['criados'] == 500
        assert ColaboradorCadastro.objects.count() == 500
