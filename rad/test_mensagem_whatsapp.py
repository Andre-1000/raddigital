"""
Mensagem "Copiar" para o WhatsApp -- formato por grupos (26/10/2026).

Regras (decisao do Andre):
  - sem linhas "___"; grupos com titulo (emoji + negrito) e linha em
    branco entre eles;
  - campo que se aplica mas ficou vazio: rotulo sem valor;
  - campo que nao se aplica: nao aparece;
  - pares explicitos: "A (início) // B (término)";
  - "Atividade" saiu; entraram Tipo de Manutenção, Tipo de Veículo e
    Operador.
Tambem confere que servidor (rad/exportacao.py) e celular
(exportar_cliente.js) geram EXATAMENTE o mesmo texto para o mesmo RAD.
"""
import json
import subprocess
from pathlib import Path

import pytest
from django.urls import reverse

from catalogos.models import CatMotivoAtraso, CatServico, CatTipoManutencao
from configuracoes.models import CampoFormulario
from rad.edicao import montar_rascunho
from rad.exportacao import gerar_mensagem_copiar
from rad.test_edicao_rad import _auth, _sincronizar, tecnico  # noqa: F401
from rad.test_numero_os import _payload, catalogo  # noqa: F401

PASTA_JS = Path(__file__).resolve().parent.parent / 'interface' / 'js_tests'


@pytest.fixture
def rad_preventiva(client, catalogo, tecnico):  # noqa: F811
    _, token = tecnico
    return _sincronizar(client, token, _payload(
        catalogo,
        hora_prog_inicio='09:30', hora_prog_termino='15:30',
        hora_real_inicio='09:53', hora_real_termino='14:42',
        km_poste_inicial='12/01 + 007', km_poste_final='14/15 + 752',
        materiais_utilizados='Marita\nChave de junta',
        descricao_tecnica_atividade='Inspeção visual do trecho.',
        observacoes_gerais='Linha 1\nLinha 2',
    ))


@pytest.fixture
def rad_falha_com_terceiros(client, catalogo, tecnico):  # noqa: F811
    falha = CatTipoManutencao.objects.create(nome='Falha')
    terceiros = CatServico.objects.create(
        nome='Roçada Teste', area='infra', requer_terceiros=True, terceiros_tem_volume=True,
    )
    _, token = tecnico
    return _sincronizar(client, token, _payload(
        catalogo,
        id_tipo_manutencao=falha.id, numero_falha=5521,
        hora_prog_inicio=None, hora_prog_termino=None,
        servicos=[terceiros.id],
        terceiros_num_encarregados=2, terceiros_num_ajudantes=3, terceiros_num_motorista=1,
        terceiros_volume=4,
        sync_id_tentativa='falha-whatsapp-1',
    ))


class TestFormato:
    def test_preventiva_por_grupos(self, rad_preventiva):
        msg = gerar_mensagem_copiar(rad_preventiva)
        assert msg.startswith('*RAD – Relatório de Atividade Diária*\n\n📋 *IDENTIFICAÇÃO*\n')
        assert '___' not in msg
        for titulo in ('📅 *DATAS E HORÁRIOS*', '📍 *LOCALIZAÇÃO*', '🛠️ *EXECUÇÃO*',
                       '👷 *RESPONSÁVEIS*', '📝 *DESCRIÇÃO TÉCNICA*', '💬 *OBSERVAÇÃO GERAL*'):
            assert f'\n\n{titulo}\n' in msg or msg.endswith(f'\n\n{titulo}')
        assert 'Tipo de Manutenção: Preventiva' in msg
        assert 'Programado: 09:30 (início) // 15:30 (término)' in msg
        assert 'Realizado: 09:53 (início) // 14:42 (término)' in msg
        assert 'Km/Poste: 12/01 + 007 (inicial) // 14/15 + 752 (final)' in msg
        assert 'Local: PTR (inicial) // PTR (final)' in msg
        assert 'Serviços realizados: Inspecao' in msg
        assert '📝 *DESCRIÇÃO TÉCNICA*\nInspeção visual do trecho.' in msg
        assert 'Equipamentos utilizados: Marita, Chave de junta' in msg  # quebra de linha vira virgula

    def test_texto_livre_mantem_quebra_de_linha(self, rad_preventiva):
        assert gerar_mensagem_copiar(rad_preventiva).endswith('💬 *OBSERVAÇÃO GERAL*\nLinha 1\nLinha 2')

    def test_atividade_saiu(self, rad_preventiva):
        linhas = gerar_mensagem_copiar(rad_preventiva).split('\n')
        assert not any(linha.startswith('Atividade:') for linha in linhas)

    def test_vazio_aparece_so_o_rotulo(self, rad_preventiva):
        linhas = gerar_mensagem_copiar(rad_preventiva).split('\n')
        assert 'Solicitante SA:' in linhas
        assert 'Tipo de Veículo:' in linhas
        assert 'Operador:' in linhas
        assert 'N/A' not in '\n'.join(linhas)

    def test_nao_se_aplica_nao_aparece(self, rad_preventiva):
        msg = gerar_mensagem_copiar(rad_preventiva)
        assert 'N° Falha' not in msg            # tipo nao e Falha
        assert rad_preventiva.atraso_inicio  # comecou atrasado (09:53 > 09:30)...
        assert 'Motivo dos atrasos' not in msg  # ...mas o formulario so pede motivo no termino
        assert 'Terceiros' not in msg           # nenhum servico pede
        assert 'Descrição de Outros' not in msg

    def test_falha_tira_programado_e_mostra_falha_e_terceiros(self, rad_falha_com_terceiros):
        msg = gerar_mensagem_copiar(rad_falha_com_terceiros)
        assert 'N° Falha: 5521' in msg
        assert 'Programado' not in msg
        assert 'N° Encarregados (Terceiros): 2' in msg
        assert 'Volume (Terceiros): 4' in msg
        assert 'Op Máquina' not in msg  # servico nao pede Op Maquina

    def test_motivo_de_atraso_aparece_quando_houve_atraso(self, client, catalogo, tecnico):  # noqa: F811
        motivo = CatMotivoAtraso.objects.create(nome='Trânsito')
        _, token = tecnico
        rad = _sincronizar(client, token, _payload(
            catalogo, hora_real_termino='13:00', id_motivo_atraso_termino=motivo.id,
            sync_id_tentativa='atraso-whatsapp-1',
        ))
        assert rad.atraso_termino
        assert 'Motivo dos atrasos: Término — Trânsito' in gerar_mensagem_copiar(rad)

    def test_campo_desabilitado_some(self, rad_preventiva):
        CampoFormulario.objects.filter(chave='responsavel_atividade').update(habilitado=False)
        assert 'Responsável Atividade' not in gerar_mensagem_copiar(rad_preventiva)


def _mensagem_no_celular(rascunho, catalogos):
    script = (
        "const vm=require('vm'),fs=require('fs');"
        "const ctx={document:{createElement:()=>({})},window:{}};vm.createContext(ctx);"
        "vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+';this.EC=ExportarCliente;',ctx);"
        "const e=JSON.parse(fs.readFileSync(0,'utf8'));"
        "process.stdout.write(ctx.EC.gerarMensagemCopiar(e.rascunho,e.catalogos));"
    )
    caminho = PASTA_JS.parent / 'static' / 'interface' / 'js' / 'exportar_cliente.js'
    resultado = subprocess.run(
        ['node', '-e', script, str(caminho)],
        input=json.dumps({'rascunho': rascunho, 'catalogos': catalogos}),
        capture_output=True, text=True, timeout=60, encoding='utf-8',
    )
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout


class TestServidorIgualCelular:
    @pytest.mark.parametrize('fixture', ['rad_preventiva', 'rad_falha_com_terceiros'])
    def test_mesmo_texto(self, request, client, tecnico, fixture):  # noqa: F811
        rad = request.getfixturevalue(fixture)
        _, token = tecnico
        catalogos = client.get(reverse('catalogos:listar_todos'), **_auth(token)).json()
        catalogos['campos_desabilitados'] = []
        rascunho = montar_rascunho(rad)
        assert _mensagem_no_celular(rascunho, catalogos) == gerar_mensagem_copiar(rad)
