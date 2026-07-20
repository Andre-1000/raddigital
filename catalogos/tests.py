"""
Testes do app catalogos.

Cobre a integridade dos modelos de catalogo e o comando de carga dos
seeds (management command carregar_catalogos).
"""
import pytest
from django.core.management import call_command
from django.db import IntegrityError

from catalogos.models import (
    CatAcaoAmv,
    CatEquipe,
    CatLinha,
    CatLocal,
    CatMch,
    CatMotivoAtraso,
    CatServico,
    CatTipoDefeitoAmv,
    CatTipoManutencao,
    CatVia,
)


@pytest.mark.django_db
class TestModelosCatalogo:
    def test_cat_linha_codigo_e_chave_primaria_unica(self):
        CatLinha.objects.create(codigo='11', nome='Coral')
        with pytest.raises(IntegrityError):
            CatLinha.objects.create(codigo='11', nome='Duplicada')

    def test_cat_local_sigla_e_chave_primaria_unica(self):
        CatLocal.objects.create(sigla='BFU', nome='Barra Funda', categoria='estacao')
        with pytest.raises(IntegrityError):
            CatLocal.objects.create(sigla='BFU', nome='Outra', categoria='patio')

    def test_cat_servico_manutencao_amv_requer_amv_true(self):
        servico = CatServico.objects.create(
            nome='Manutenção em AMV', requer_amv=True
        )
        assert servico.requer_amv is True
        assert servico.requer_descricao is False

    def test_cat_servico_outros_requer_descricao_true(self):
        servico = CatServico.objects.create(nome='Outros', requer_descricao=True)
        assert servico.requer_descricao is True

    def test_cat_mch_identificacao_unica(self):
        CatMch.objects.create(
            identificacao='MCH01A-L31',
            modelo='MD-2000',
            via='1',
            ur='UR 31',
            local_amv='CVN',
            linha='11',
        )
        with pytest.raises(IntegrityError):
            CatMch.objects.create(
                identificacao='MCH01A-L31',
                modelo='OUTRO',
                via='2',
                ur='UR 32',
                local_amv='SUZ',
                linha='11',
            )

    def test_cat_mch_via_pode_ficar_vazia_pendencia_conhecida(self):
        """MCH29U-BFU tem a via pendente de preenchimento (item bloqueante 8.1)."""
        mch = CatMch.objects.create(
            identificacao='MCH29U-BFU',
            modelo='M23-E',
            via='',
            ur='BFU',
            local_amv='BFU',
            linha='11',
        )
        assert mch.via == ''

    def test_cat_tipo_manutencao_nome_unico(self):
        CatTipoManutencao.objects.create(nome='Falha')
        with pytest.raises(IntegrityError):
            CatTipoManutencao.objects.create(nome='Falha')

    def test_cat_via_nome_unico(self):
        CatVia.objects.create(nome='Via 1')
        with pytest.raises(IntegrityError):
            CatVia.objects.create(nome='Via 1')

    def test_cat_motivo_atraso_nome_unico(self):
        CatMotivoAtraso.objects.create(nome='Clima')
        with pytest.raises(IntegrityError):
            CatMotivoAtraso.objects.create(nome='Clima')

    def test_cat_tipo_defeito_amv_nome_unico(self):
        CatTipoDefeitoAmv.objects.create(nome='DESGASTE')
        with pytest.raises(IntegrityError):
            CatTipoDefeitoAmv.objects.create(nome='DESGASTE')

    def test_cat_acao_amv_nome_unico(self):
        CatAcaoAmv.objects.create(nome='LUBRIFICAÇÃO')
        with pytest.raises(IntegrityError):
            CatAcaoAmv.objects.create(nome='LUBRIFICAÇÃO')


@pytest.mark.django_db
class TestCargaDeSeeds:
    def test_comando_carrega_todos_os_catalogos_com_totais_corretos(self):
        """
        Executa o comando real (le os arquivos seeds_sql/*.sql do projeto)
        e confere os totais informados nos proprios arquivos seed.
        """
        call_command('carregar_catalogos')

        assert CatLinha.objects.count() == 3
        assert CatLocal.objects.count() == 70
        assert CatTipoManutencao.objects.count() == 4
        assert CatVia.objects.count() == 5
        assert CatServico.objects.count() == 13
        assert CatMotivoAtraso.objects.count() == 4
        assert CatMch.objects.count() == 238
        assert CatTipoDefeitoAmv.objects.count() == 17
        assert CatAcaoAmv.objects.count() == 7

    def test_mch29u_bfu_permanece_com_via_vazia_apos_carga(self):
        """Confirma que a pendencia conhecida nao foi mascarada pelo seed."""
        call_command('carregar_catalogos')
        mch = CatMch.objects.get(identificacao='MCH29U-BFU')
        assert mch.via == ''


@pytest.mark.django_db
class TestListarTodosCatalogos:
    """GET /catalogos/todos/ — endpoint para popular o IndexedDB do cliente."""

    def test_requer_token(self, client):
        from django.urls import reverse

        resposta = client.get(reverse('catalogos:listar_todos'))
        assert resposta.status_code == 401

    def test_retorna_todas_as_chaves_esperadas(self, client):
        from django.urls import reverse

        from usuarios.models import Token, Usuario

        usuario = Usuario.objects.create(login='tec.catalogos')
        token = Token.gerar_para(usuario)

        resposta = client.get(
            reverse('catalogos:listar_todos'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        assert resposta.status_code == 200
        corpo = resposta.json()
        for chave in (
            'linhas', 'locais', 'vias', 'equipes', 'tipos_manutencao', 'servicos',
            'motivos_atraso', 'mch', 'tipos_defeito_amv', 'acoes_amv',
        ):
            assert chave in corpo, f'Chave "{chave}" ausente na resposta.'

    def test_dados_reais_aparecem_na_resposta(self, client):
        from django.urls import reverse

        from usuarios.models import Token, Usuario

        usuario = Usuario.objects.create(login='tec.catalogos2')
        token = Token.gerar_para(usuario)
        CatLinha.objects.create(codigo='11', nome='Coral')
        CatVia.objects.create(nome='Via 1')
        CatEquipe.objects.create(codigo='VP', nome='VP')
        CatLocal.objects.create(sigla='BFU', nome='Barra Funda', categoria='estacao')
        CatTipoManutencao.objects.create(nome='Preventiva')
        CatServico.objects.create(nome='Inspeção')

        resposta = client.get(
            reverse('catalogos:listar_todos'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        corpo = resposta.json()
        assert corpo['linhas'] == [{'codigo': '11', 'nome': 'Coral'}]
        assert corpo['equipes'] == [{'codigo': 'VP', 'nome': 'VP'}]
        assert len(corpo['locais']) == 1
        assert len(corpo['servicos']) == 1

    def test_servico_inativo_nao_aparece(self, client):
        from django.urls import reverse

        from usuarios.models import Token, Usuario

        usuario = Usuario.objects.create(login='tec.catalogos3')
        token = Token.gerar_para(usuario)
        CatServico.objects.create(nome='Ativo', ativo=True)
        CatServico.objects.create(nome='Inativo', ativo=False)

        resposta = client.get(
            reverse('catalogos:listar_todos'), HTTP_AUTHORIZATION=f'Token {token.token}'
        )
        nomes = [s['nome'] for s in resposta.json()['servicos']]
        assert 'Ativo' in nomes
        assert 'Inativo' not in nomes
