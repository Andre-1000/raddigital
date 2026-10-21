"""
Filtro de Consulta por servico DESATIVADO (15/10/2026).

Contexto: "Inspeção (Geral)" e "Reparo (Geral)" foram desativados em
14/10/2026 (catalogos 0013). O Administrador precisa achar os RADs
antigos que os usam para reclassificar -- entao a tela de Consulta lista
tambem os desativados na Subcategoria, mas o formulario de
preenchimento (que guarda o catalogo offline) NUNCA pode recebe-los.
"""
import pytest
from django.urls import reverse

from catalogos.models import CatServico
from rad.test_edicao_rad import _auth, _sincronizar, admin, tecnico  # noqa: F401
from rad.test_numero_os import _payload, catalogo  # noqa: F401


@pytest.fixture
def servico_desativado(db):
    return CatServico.objects.create(nome='Servico Antigo Teste', area='geral', ativo=False)


class TestCatalogo:
    def test_sem_parametro_nao_traz_desativados(self, client, tecnico, servico_desativado):  # noqa: F811
        _, token = tecnico
        dados = client.get(reverse('catalogos:listar_todos'), **_auth(token)).json()
        assert 'servicos_desativados' not in dados
        assert servico_desativado.id not in [s['id'] for s in dados['servicos']]

    def test_com_parametro_traz_desativados_em_chave_separada(self, client, tecnico, servico_desativado):  # noqa: F811
        _, token = tecnico
        dados = client.get(
            reverse('catalogos:listar_todos') + '?incluir_servicos_desativados=1', **_auth(token)
        ).json()
        assert {'id': servico_desativado.id, 'nome': 'Servico Antigo Teste', 'area': 'geral'} in dados['servicos_desativados']
        # 'servicos' continua so com ativos (o formulario le essa chave)
        assert servico_desativado.id not in [s['id'] for s in dados['servicos']]


class TestFiltroConsulta:
    def test_filtra_rads_pelo_servico_desativado(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tecnico = tecnico
        rad_antigo = _sincronizar(client, token_tecnico, _payload(catalogo))
        outro = CatServico.objects.create(nome='Outro Servico Teste', area='geral')
        rad_outro = _sincronizar(
            client, token_tecnico, _payload(catalogo, numero_os=9999, servicos=[outro.id], sync_id_tentativa='outro-rad-teste')
        )

        antigo = catalogo['servico']
        antigo.ativo = False
        antigo.save()

        _, token = admin
        resposta = client.get(
            reverse('consulta:listar_rads') + f'?servico_ids={antigo.id}', **_auth(token)
        )
        assert resposta.status_code == 200
        numeros = [r['numero_rad'] for r in resposta.json()['resultados']]
        assert rad_antigo.numero_rad in numeros
        assert rad_outro.numero_rad not in numeros
