"""
Teste de exportacao offline (RG-EXP-001 a 010) com navegador real.

jsPDF precisa de atob/canvas de navegador de verdade -- nem jsdom nem
Node puro servem para isso. Este teste sobe um servidor Django de
verdade, abre no Chromium, preenche o formulario o suficiente para
habilitar o botao Exportar (RG-EXP-005), **desliga a rede de verdade**,
clica em "Baixar PDF", e confirma que o download aconteceu e que o
conteudo do PDF baixado contem os dados reais do RAD -- prova que a
exportacao funciona sem nenhuma chamada ao servidor.
"""
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def _esperar_servidor(url, tentativas=30, intervalo=0.5):
    for _ in range(tentativas):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(intervalo)
    return False


@pytest.fixture
def servidor_django():
    porta = _porta_livre()
    processo = subprocess.Popen(
        ['python', 'manage.py', 'runserver', f'127.0.0.1:{porta}', '--noreload'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(BASE_DIR),
    )
    base_url = f'http://127.0.0.1:{porta}'
    if not _esperar_servidor(f'{base_url}/entrar/'):
        processo.terminate()
        raise RuntimeError('Servidor Django nao respondeu a tempo.')
    yield base_url
    processo.terminate()
    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        processo.kill()


def _extrair_texto_pdf(caminho):
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho))
    return ''.join(pagina.extract_text() for pagina in leitor.pages)


@pytest.mark.django_db(transaction=True)
class TestExportarOfflineComNavegadorReal:
    def test_pdf_gerado_offline_contem_os_dados_do_rad(self, servidor_django, tmp_path):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            navegador = p.chromium.launch()
            try:
                contexto = navegador.new_context()
                pagina = contexto.new_page()

                pagina.add_init_script(
                    """
                    localStorage.setItem('rad_sessao', JSON.stringify({
                        login: 'tecnico.teste.exportar',
                        token: 'token-fake-so-para-navegacao',
                        validade: '2099-01-01T00:00:00Z',
                        perfis: ['usuario'],
                    }));
                    """
                )

                pagina.goto(f'{servidor_django}/novo-rad/')
                pagina.wait_for_timeout(500)

                pagina.evaluate(
                    """
                    async () => {
                        const rascunho = {
                            numero_os: 4321, numero_sa: '9999999999',
                            data_preenchimento: '2026-07-17',
                            id_local_inicial: 'ZZZ', id_local_final: 'ZZZ',
                            linhas: ['99'], vias: [1], equipes: ['VP'],
                            km_poste: '', id_tipo_manutencao: 1, numero_falha: null,
                            hora_prog_inicio: '08:00', data_hp_inicio: '2026-07-17',
                            hora_prog_termino: '12:00', data_hp_termino: '2026-07-17',
                            hora_real_inicio: '08:00', data_hr_inicio: '2026-07-17',
                            hora_real_termino: '12:00', data_hr_termino: '2026-07-17',
                            id_motivo_atraso_inicio: null, desc_motivo_atraso_inicio: '',
                            id_motivo_atraso_termino: null, desc_motivo_atraso_termino: '',
                            servicos: [1], outros_servico_desc: '',
                            amv: {id_mch: null, tipos_defeito: [], acoes: []},
                            colaboradores: [{registro_empresa: null, nome: 'Fulano Offline', tipo: 'participante'}],
                            anexos: {fotos_intervencao_verificada: [], fotos_acao_realizada: [], pdf: []},
                            responsavel_atividade: 'Responsavel Offline Teste',
                            operador_ccm: '', descricao_tecnica_atividade: '',
                            materiais_utilizados: '', observacoes_gerais: '',
                            sync_id_tentativa: 'export-offline-teste',
                        };
                        await RadDB.salvarRascunho('tecnico.teste.exportar', rascunho);
                    }
                    """
                )

                pagina.reload()
                pagina.wait_for_timeout(500)

                # O rascunho injetado tem conteudo relevante (numero_os,
                # servicos), entao a regra "um RAD por vez" (RG-SYNC-018/019)
                # pergunta antes de mostrar o formulario -- precisa
                # continuar para chegar no botao Exportar.
                modal_conflito = pagina.locator('#modal-conflito-rascunho')
                if modal_conflito.is_visible():
                    pagina.click('#botao-continuar-rascunho')
                    pagina.wait_for_timeout(200)

                botao_exportar = pagina.locator('#botao-exportar')
                assert not botao_exportar.is_disabled(), (
                    'RG-EXP-005: botao Exportar deveria estar habilitado com '
                    'todos os campos obrigatorios preenchidos'
                )

                contexto.set_offline(True)

                botao_exportar.click()
                pagina.wait_for_timeout(200)

                with pagina.expect_download() as info_download:
                    pagina.click('#botao-exportar-pdf')
                download = info_download.value

                caminho_pdf = tmp_path / 'exportado_offline.pdf'
                download.save_as(str(caminho_pdf))
                conteudo = caminho_pdf.read_bytes()

                assert conteudo.startswith(b'%PDF'), 'arquivo baixado offline e um PDF valido'

                texto_pdf = _extrair_texto_pdf(caminho_pdf)
                assert '4321' in texto_pdf, 'PDF gerado offline contem a OS do rascunho'
                assert 'Offline Teste' in texto_pdf, (
                    'PDF gerado offline contem o responsavel_atividade do rascunho'
                )
            finally:
                navegador.close()
