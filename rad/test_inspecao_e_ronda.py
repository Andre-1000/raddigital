"""
Testes do bloco "Inspeção e Ronda" em Servicos Executados (14/10/2026).

Cobre:
  - migration catalogos 0013 (funcoes aplicar/reverter): renomeia e
    desativa os antigos "Inspeção"/"Reparo" do Geral sem mudar os RADs
    antigos de grupo, e cria os novos na area 'insp_ronda';
  - ordem alfabetica dos blocos (AREA_CHOICES e detalhe da Consulta);
  - edicao de RAD antigo: o servico desativado aparece em
    'servicos_desativados' e pode ser trocado pelo novo.
"""
import importlib

import pytest
from django.apps import apps as django_apps
from django.urls import reverse

from catalogos.models import CatServico
from consulta.views import _servicos_por_area
from rad.models import RadServico
from rad.test_edicao_rad import _auth, _editar, _sincronizar, admin, tecnico  # noqa: F401
from rad.test_numero_os import _payload, catalogo  # noqa: F401

migracao = importlib.import_module('catalogos.migrations.0013_inspecao_e_ronda')


@pytest.fixture
def servicos_antigos(db):
    """Estado de producao ANTES da 0013: Inspeção/Reparo ativos no Geral."""
    CatServico.objects.filter(nome__in=['Inspeção', 'Reparo', 'Inspeção (Geral)', 'Reparo (Geral)']).delete()
    return {
        'inspecao': CatServico.objects.create(nome='Inspeção', area='geral', descricao='Desc inspeção'),
        'reparo': CatServico.objects.create(nome='Reparo', area='geral', descricao='Desc reparo'),
    }


class TestMigracao:
    def test_aplicar_renomeia_desativa_e_cria_novos(self, servicos_antigos):
        migracao.aplicar(django_apps, None)

        antigo = CatServico.objects.get(pk=servicos_antigos['inspecao'].pk)
        assert antigo.nome == 'Inspeção (Geral)'
        assert antigo.area == 'geral'
        assert antigo.ativo is False

        novo = CatServico.objects.get(nome='Inspeção')
        assert novo.pk != antigo.pk
        assert novo.area == 'insp_ronda'
        assert novo.ativo is True
        assert novo.descricao == 'Desc inspeção'

        assert CatServico.objects.get(nome='Reparo').area == 'insp_ronda'
        assert CatServico.objects.get(nome='Reparo (Geral)').ativo is False

    def test_aplicar_duas_vezes_nao_duplica(self, servicos_antigos):
        migracao.aplicar(django_apps, None)
        migracao.aplicar(django_apps, None)
        nomes = ['Inspeção', 'Inspeção (Geral)', 'Reparo', 'Reparo (Geral)']
        assert CatServico.objects.filter(nome__in=nomes).count() == 4
        assert CatServico.objects.filter(area='insp_ronda').count() == 2

    def test_reverter_volta_ao_estado_anterior(self, servicos_antigos):
        migracao.aplicar(django_apps, None)
        migracao.reverter(django_apps, None)

        antigo = CatServico.objects.get(pk=servicos_antigos['inspecao'].pk)
        assert (antigo.nome, antigo.area, antigo.ativo) == ('Inspeção', 'geral', True)
        assert not CatServico.objects.filter(area='insp_ronda').exists()


class TestOrdemDosBlocos:
    def test_area_choices_em_ordem_alfabetica_do_rotulo(self):
        rotulos = [rotulo for _codigo, rotulo in CatServico.AREA_CHOICES]
        assert rotulos == sorted(rotulos)
        assert ('insp_ronda', 'Inspeção e Ronda') in CatServico.AREA_CHOICES

    def test_chave_cabe_na_coluna(self):
        limite = CatServico._meta.get_field('area').max_length
        assert all(len(codigo) <= limite for codigo, _ in CatServico.AREA_CHOICES)

    def test_detalhe_da_consulta_agrupa_em_ordem_alfabetica(self, client, catalogo, tecnico):  # noqa: F811
        ronda = CatServico.objects.create(nome='Reparo Teste', area='insp_ronda')
        amv = CatServico.objects.create(nome='Inspeção AMV Teste', area='amv')
        _, token = tecnico
        rad = _sincronizar(
            client, token, _payload(catalogo, servicos=[catalogo['servico'].id, ronda.id, amv.id])
        )
        areas = [grupo['area'] for grupo in _servicos_por_area(rad)]
        assert areas == ['AMV', 'Geral', 'Inspeção e Ronda']


class TestEdicaoDeRadAntigo:
    @pytest.fixture
    def rad_com_servico_desativado(self, client, catalogo, tecnico):  # noqa: F811
        _, token = tecnico
        rad = _sincronizar(client, token, _payload(catalogo))
        servico = catalogo['servico']
        servico.nome = 'Inspecao (Geral)'
        servico.ativo = False
        servico.save()
        return rad

    def test_dados_edicao_traz_servico_desativado(self, client, admin, rad_com_servico_desativado, catalogo):  # noqa: F811
        _, token = admin
        resposta = client.get(
            reverse('rad:dados_edicao', args=[rad_com_servico_desativado.numero_rad]), **_auth(token)
        )
        assert resposta.status_code == 200
        desativados = resposta.json()['servicos_desativados']
        assert [s['id'] for s in desativados] == [catalogo['servico'].id]
        assert desativados[0]['nome'] == 'Inspecao (Geral)'
        assert desativados[0]['area'] == 'geral'

    def test_rad_so_com_servicos_ativos_nao_traz_desativados(self, client, admin, catalogo, tecnico):  # noqa: F811
        _, token_tecnico = tecnico
        rad = _sincronizar(client, token_tecnico, _payload(catalogo))
        _, token = admin
        resposta = client.get(reverse('rad:dados_edicao', args=[rad.numero_rad]), **_auth(token))
        assert resposta.json()['servicos_desativados'] == []

    def test_admin_troca_servico_antigo_pelo_novo(self, client, admin, rad_com_servico_desativado, catalogo):  # noqa: F811
        novo = CatServico.objects.create(nome='Inspeção Ronda Teste', area='insp_ronda')
        _, token = admin
        resposta = _editar(
            client, token, rad_com_servico_desativado.numero_rad,
            _payload(catalogo, servicos=[novo.id]), motivo='Reclassificação para Inspeção e Ronda',
        )
        assert resposta.status_code == 200, resposta.content
        ids = list(RadServico.objects.filter(rad=rad_com_servico_desativado).values_list('servico_id', flat=True))
        assert ids == [novo.id]
