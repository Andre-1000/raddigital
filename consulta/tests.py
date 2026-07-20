"""
Testes do app consulta — PRM-028 a PRM-038.
"""
import json

import pytest
from django.urls import reverse

from catalogos.models import CatEquipe, CatLinha, CatLocal, CatServico, CatTipoManutencao, CatVia
from usuarios.models import Token, Usuario, UsuarioPerfil


@pytest.fixture
def catalogo(db):
    return {
        'local': CatLocal.objects.create(sigla='BFU', nome='Barra Funda', categoria='estacao'),
        'linha': CatLinha.objects.create(codigo='11', nome='Coral'),
        'via': CatVia.objects.create(nome='Via 1'),
        'tipo_manutencao': CatTipoManutencao.objects.create(nome='Preventiva'),
        'equipe_vp': CatEquipe.objects.get_or_create(codigo='VP', defaults={'nome': 'VP'})[0],
        'servico': CatServico.objects.create(nome='Inspecao'),
    }


def _payload(catalogo, numero_os, sync_id):
    return {
        'numero_os': numero_os,
        'numero_sa': '1357',
        'responsavel_atividade': 'Responsavel Teste',
        'data_preenchimento': '2026-06-15',
        'id_local_inicial': catalogo['local'].sigla,
        'id_local_final': catalogo['local'].sigla,
        'linhas': [catalogo['linha'].codigo],
        'vias': [catalogo['via'].id],
        'id_tipo_manutencao': catalogo['tipo_manutencao'].id,
        'hora_prog_inicio': '08:00',
        'hora_prog_termino': '12:00',
        'hora_real_inicio': '08:00',
        'hora_real_termino': '12:00',
        'servicos': [catalogo['servico'].id],
        'colaboradores': [{'registro_empresa': '1', 'nome': 'Tec', 'tipo': 'participante'}],
        'sync_id_tentativa': sync_id,
    }


def _criar_tecnico_com_token():
    usuario = Usuario.objects.create(login=f'tec.{Usuario.objects.count()}')
    return usuario, Token.gerar_para(usuario)


def _sincronizar(client, catalogo, numero_os, sync_id):
    _, token = _criar_tecnico_com_token()
    resposta = client.post(
        reverse('rad:sincronizar'),
        data=json.dumps(_payload(catalogo, numero_os, sync_id)),
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Token {token.token}',
    )
    assert resposta.status_code == 201
    return resposta.json()['numero_rad']


@pytest.fixture
def supervisor_com_token(db):
    usuario = Usuario.objects.create(login='supervisor.consulta')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.SUPERVISOR)
    return usuario, Token.gerar_para(usuario)


@pytest.fixture
def administrador_com_token(db):
    usuario = Usuario.objects.create(login='admin.consulta')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.ADMINISTRADOR)
    return usuario, Token.gerar_para(usuario)


@pytest.fixture
def usuario_comum_com_token(db):
    usuario = Usuario.objects.create(login='comum.consulta')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.USUARIO)
    return usuario, Token.gerar_para(usuario)


@pytest.mark.django_db
class TestPermissaoConsulta:
    def test_usuario_comum_nao_acessa_listagem(
        self, client, usuario_comum_com_token, catalogo
    ):
        _, token = usuario_comum_com_token
        resposta = client.get(
            reverse('consulta:listar_rads'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        assert resposta.status_code == 403

    def test_supervisor_acessa_listagem(self, client, supervisor_com_token, catalogo):
        _, token = supervisor_com_token
        resposta = client.get(
            reverse('consulta:listar_rads'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        assert resposta.status_code == 200

    def test_administrador_acessa_listagem(self, client, administrador_com_token, catalogo):
        _, token = administrador_com_token
        resposta = client.get(
            reverse('consulta:listar_rads'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        assert resposta.status_code == 200


@pytest.mark.django_db
class TestListagemEFiltros:
    def test_filtro_numero_os_retorna_apenas_correspondentes(
        self, client, supervisor_com_token, catalogo
    ):
        _, token = supervisor_com_token
        _sincronizar(client, catalogo, 1111, 'filtro-sa-1')
        _sincronizar(client, catalogo, 2222, 'filtro-sa-2')

        resposta = client.get(
            reverse('consulta:listar_rads'),
            {'numero_os': 1111},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        corpo = resposta.json()
        assert corpo['total_encontrado'] == 1
        assert corpo['resultados'][0]['numero_os'] == 1111

    def test_filtros_multiplos_aplicam_and(self, client, supervisor_com_token, catalogo):
        """PRM-028: mais de um filtro aplicado simultaneamente (AND)."""
        _, token = supervisor_com_token
        _sincronizar(client, catalogo, 3333, 'filtro-and-1')

        resposta = client.get(
            reverse('consulta:listar_rads'),
            {'numero_os': 3333, 'status': 'cancelado'},  # status nao bate
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.json()['total_encontrado'] == 0

    def test_paginacao_15_por_pagina(self, client, supervisor_com_token, catalogo):
        """PRM-032."""
        _, token = supervisor_com_token
        for i in range(17):
            _sincronizar(client, catalogo, 5000 + i, f'paginacao-{i}')

        resposta = client.get(
            reverse('consulta:listar_rads'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        corpo = resposta.json()
        assert corpo['total_encontrado'] == 17
        assert len(corpo['resultados']) == 15
        assert corpo['total_paginas'] == 2

    def test_total_encontrado_exibido(self, client, supervisor_com_token, catalogo):
        """PRM-031."""
        _, token = supervisor_com_token
        _sincronizar(client, catalogo, 6000, 'total-1')
        _sincronizar(client, catalogo, 6001, 'total-2')

        resposta = client.get(
            reverse('consulta:listar_rads'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        assert resposta.json()['total_encontrado'] == 2


    def test_filtro_login_usuario(self, client, supervisor_com_token, catalogo):
        _, token = supervisor_com_token
        _sincronizar(client, catalogo, 8000, 'filtro-login')

        resposta_sem_filtro = client.get(
            reverse('consulta:listar_rads'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        login_criador = resposta_sem_filtro.json()['resultados'][0]['login_usuario']

        resposta = client.get(
            reverse('consulta:listar_rads'),
            {'login_usuario': login_criador},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.json()['total_encontrado'] == 1

        resposta_outro_login = client.get(
            reverse('consulta:listar_rads'),
            {'login_usuario': 'login.que.nao.existe'},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta_outro_login.json()['total_encontrado'] == 0

    def test_filtro_data_de_ate(self, client, supervisor_com_token, catalogo):
        """RADs sao sempre criados com data_preenchimento=2026-06-15 nos testes."""
        _, token = supervisor_com_token
        _sincronizar(client, catalogo, 8100, 'filtro-data')

        dentro = client.get(
            reverse('consulta:listar_rads'),
            {'data_de': '2026-06-14', 'data_ate': '2026-06-16'},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert dentro.json()['total_encontrado'] == 1

        fora = client.get(
            reverse('consulta:listar_rads'),
            {'data_de': '2026-07-01'},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert fora.json()['total_encontrado'] == 0

    def test_filtro_local_e_tipo_manutencao(self, client, supervisor_com_token, catalogo):
        _, token = supervisor_com_token
        _sincronizar(client, catalogo, 8200, 'filtro-local-tipo')

        resposta = client.get(
            reverse('consulta:listar_rads'),
            {
                'id_local_inicial': catalogo['local'].sigla,
                'id_local_final': catalogo['local'].sigla,
                'id_tipo_manutencao': catalogo['tipo_manutencao'].id,
            },
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.json()['total_encontrado'] == 1

    def test_filtro_hp_inicio_e_hr_inicio(self, client, supervisor_com_token, catalogo):
        """RADs de teste tem HP/HR Inicio as 08:00 de 2026-06-15."""
        _, token = supervisor_com_token
        _sincronizar(client, catalogo, 8300, 'filtro-horario')

        dentro = client.get(
            reverse('consulta:listar_rads'),
            {
                'hp_inicio_de': '2026-06-15T00:00',
                'hp_inicio_ate': '2026-06-15T23:59',
                'hr_inicio_de': '2026-06-15T00:00',
                'hr_inicio_ate': '2026-06-15T23:59',
            },
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert dentro.json()['total_encontrado'] == 1

        fora = client.get(
            reverse('consulta:listar_rads'),
            {'hp_inicio_de': '2026-06-16T00:00'},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert fora.json()['total_encontrado'] == 0

    def test_filtro_id_mch_e_linha_mch(self, client, supervisor_com_token, catalogo):
        from catalogos.models import CatAcaoAmv, CatMch, CatTipoDefeitoAmv

        _, token = supervisor_com_token
        mch = CatMch.objects.create(
            identificacao='MCH01A-BFU', modelo='M23-E', via='3', ur='BFU',
            local_amv='BFU', linha='11',
        )
        servico_amv = CatServico.objects.create(nome='Manutencao em AMV', requer_amv=True)
        defeito = CatTipoDefeitoAmv.objects.create(nome='DESGASTE')
        acao = CatAcaoAmv.objects.create(nome='LUBRIFICACAO')

        _, token_tecnico = _criar_tecnico_com_token()
        payload = _payload(catalogo, 8400, 'filtro-mch')
        payload['servicos'].append(servico_amv.id)
        payload['amv'] = {'id_mch': mch.id, 'tipos_defeito': [defeito.id], 'acoes': [acao.id]}
        resposta_sync = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token_tecnico.token}',
        )
        assert resposta_sync.status_code == 201

        resposta = client.get(
            reverse('consulta:listar_rads'),
            {'id_mch': mch.id, 'linha_mch': '11'},
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.json()['total_encontrado'] == 1


@pytest.mark.django_db
class TestDetalheRad:
    def test_detalhe_traz_campos_multiplos_e_anexos(
        self, client, supervisor_com_token, catalogo
    ):
        """PRM-036."""
        _, token = supervisor_com_token
        numero_rad = _sincronizar(client, catalogo, 7000, 'detalhe-1')

        resposta = client.get(
            reverse('consulta:detalhe_rad', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['linhas'] == [catalogo['linha'].codigo]
        assert corpo['servicos'] == [catalogo['servico'].nome]
        assert len(corpo['colaboradores']) == 1
        assert corpo['anexos'] == []

    def test_supervisor_nao_pode_cancelar(self, client, supervisor_com_token, catalogo):
        """PRM-037: Supervisor nao ve/nao pode acionar cancelamento."""
        _, token = supervisor_com_token
        numero_rad = _sincronizar(client, catalogo, 7001, 'detalhe-2')

        resposta = client.get(
            reverse('consulta:detalhe_rad', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.json()['pode_cancelar'] is False

    def test_administrador_pode_cancelar_rad_ativo(
        self, client, administrador_com_token, catalogo
    ):
        _, token = administrador_com_token
        numero_rad = _sincronizar(client, catalogo, 7002, 'detalhe-3')

        resposta = client.get(
            reverse('consulta:detalhe_rad', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.json()['pode_cancelar'] is True

    def test_rad_inexistente_retorna_404(self, client, supervisor_com_token):
        _, token = supervisor_com_token
        resposta = client.get(
            reverse('consulta:detalhe_rad', args=['R99999']),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 404

    def test_campo_desabilitado_desaparece_do_detalhe_para_supervisor_e_admin(
        self, client, supervisor_com_token, administrador_com_token, catalogo
    ):
        """
        Mudanca de negocio (17/07/2026): campo desabilitado nao aparece
        para NINGUEM, nem Supervisor nem Administrador.
        """
        from configuracoes.models import CampoFormulario

        _, token_supervisor = supervisor_com_token
        _, token_admin = administrador_com_token
        numero_rad = _sincronizar(client, catalogo, 7003, 'detalhe-campo-desabilitado')

        CampoFormulario.objects.filter(chave='observacoes_gerais').update(habilitado=False)
        try:
            resposta_supervisor = client.get(
                reverse('consulta:detalhe_rad', args=[numero_rad]),
                HTTP_AUTHORIZATION=f'Token {token_supervisor.token}',
            )
            resposta_admin = client.get(
                reverse('consulta:detalhe_rad', args=[numero_rad]),
                HTTP_AUTHORIZATION=f'Token {token_admin.token}',
            )
            assert 'observacoes_gerais' not in resposta_supervisor.json()
            assert 'observacoes_gerais' not in resposta_admin.json()
        finally:
            CampoFormulario.objects.filter(chave='observacoes_gerais').update(habilitado=True)

        # Reabilitado: volta a aparecer normalmente
        resposta_depois = client.get(
            reverse('consulta:detalhe_rad', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token_supervisor.token}',
        )
        assert 'observacoes_gerais' in resposta_depois.json()

    def test_campo_desabilitado_desaparece_tambem_da_listagem(
        self, client, supervisor_com_token, catalogo
    ):
        from configuracoes.models import CampoFormulario

        _, token = supervisor_com_token
        _sincronizar(client, catalogo, 7004, 'listagem-campo-desabilitado')

        CampoFormulario.objects.filter(chave='numero_sa').update(habilitado=False)
        try:
            resposta = client.get(
                reverse('consulta:listar_rads'), HTTP_AUTHORIZATION=f'Token {token.token}'
            )
            assert all('numero_sa' not in r for r in resposta.json()['resultados'])
        finally:
            CampoFormulario.objects.filter(chave='numero_sa').update(habilitado=True)


def _sincronizar_com_token(client, catalogo, numero_os, sync_id):
    """Como _sincronizar, mas tambem devolve o token do criador do RAD."""
    tecnico, token = _criar_tecnico_com_token()
    resposta = client.post(
        reverse('rad:sincronizar'),
        data=json.dumps(_payload(catalogo, numero_os, sync_id)),
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Token {token.token}',
    )
    assert resposta.status_code == 201
    return resposta.json()['numero_rad'], tecnico, token


@pytest.mark.django_db
class TestExportacao:
    def test_criador_do_rad_acessa_mensagem_e_pdf(self, client, catalogo):
        numero_rad, _, token_criador = _sincronizar_com_token(
            client, catalogo, 8500, 'export-criador'
        )

        resposta_msg = client.get(
            reverse('consulta:mensagem_copiar', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token_criador.token}',
        )
        resposta_pdf = client.get(
            reverse('consulta:exportar_pdf', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token_criador.token}',
        )
        assert resposta_msg.status_code == 200
        assert 'RAD - (Relatório de Atividade Diária)' in resposta_msg.json()['mensagem']
        assert resposta_pdf.status_code == 200
        assert resposta_pdf['Content-Type'] == 'application/pdf'
        assert resposta_pdf.content.startswith(b'%PDF')

        resposta_docx = client.get(
            reverse('consulta:exportar_docx', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token_criador.token}',
        )
        assert resposta_docx.status_code == 200
        assert resposta_docx.content.startswith(b'PK')

    def test_outro_tecnico_nao_acessa_rad_alheio(self, client, catalogo):
        numero_rad, _, _ = _sincronizar_com_token(client, catalogo, 8501, 'export-outro')
        _, token_outro = _criar_tecnico_com_token()

        resposta = client.get(
            reverse('consulta:mensagem_copiar', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token_outro.token}',
        )
        assert resposta.status_code == 403

    def test_supervisor_acessa_qualquer_rad(self, client, catalogo, supervisor_com_token):
        numero_rad, _, _ = _sincronizar_com_token(client, catalogo, 8502, 'export-supervisor')
        _, token_supervisor = supervisor_com_token

        resposta = client.get(
            reverse('consulta:mensagem_copiar', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token_supervisor.token}',
        )
        assert resposta.status_code == 200

    def test_administrador_acessa_qualquer_rad(self, client, catalogo, administrador_com_token):
        numero_rad, _, _ = _sincronizar_com_token(client, catalogo, 8503, 'export-admin')
        _, token_admin = administrador_com_token

        resposta = client.get(
            reverse('consulta:exportar_pdf', args=[numero_rad]),
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )
        assert resposta.status_code == 200

    def test_sem_token_retorna_401(self, client, catalogo):
        numero_rad, _, _ = _sincronizar_com_token(client, catalogo, 8504, 'export-sem-token')
        resposta = client.get(reverse('consulta:mensagem_copiar', args=[numero_rad]))
        assert resposta.status_code == 401

    def test_rad_inexistente_retorna_404(self, client, catalogo):
        _, token = _criar_tecnico_com_token()
        resposta = client.get(
            reverse('consulta:mensagem_copiar', args=['R99999']),
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 404
