"""
Teste do Service Worker com navegador real (Playwright + Chromium).

Diferente dos testes com jsdom (interface/js_tests/), este e o UNICO
jeito de testar Service Worker de verdade: jsdom nao implementa a Cache
API nem os eventos install/activate/fetch de um Service Worker. Aqui
sobe um servidor Django de verdade, abre num Chromium de verdade,
deixa o Service Worker instalar e cachear o app shell, e entao
**desliga a rede de verdade** (context.set_offline) para confirmar que
a pagina ainda carrega -- a prova real de RG-SYNC-001/010/011.

Sobe o servidor Django como subprocesso dentro do PROPRIO teste (nao
depende de um servidor ja rodando em outro lugar), entao e
autocontido e pode rodar em qualquer maquina/CI que tenha Playwright
com Chromium instalado (`playwright install chromium`).
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
    """Sobe manage.py runserver de verdade, como subprocesso, so para este teste."""
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
        raise RuntimeError('Servidor Django nao respondeu a tempo para o teste de Service Worker.')

    yield base_url

    processo.terminate()
    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        processo.kill()


@pytest.mark.django_db(transaction=True)
class TestServiceWorkerComNavegadorReal:
    def test_app_shell_funciona_offline_apos_primeiro_carregamento(self, servidor_django):
        """
        O teste central deste modulo: carrega /novo-rad/ uma vez (com
        conexao, para o Service Worker instalar e cachear), desliga a
        rede de verdade, recarrega a MESMA URL, e confirma que a pagina
        ainda carrega -- servida pelo cache do Service Worker, nao pela
        rede. Isso e RG-SYNC-001/010/011 provado de verdade, nao
        deduzido da leitura do codigo.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            navegador = p.chromium.launch()
            try:
                contexto = navegador.new_context()
                pagina = contexto.new_page()

                pagina.goto(f'{servidor_django}/novo-rad/')
                # Espera o Service Worker realmente ativar antes de seguir.
                # navigator.serviceWorker.ready as vezes resolve um instante
                # antes do estado interno virar 'activated' -- espera curta
                # com poucas tentativas evita flakiness sem mascarar um
                # problema real (se nunca ativar, o teste ainda falha).
                estado = pagina.evaluate(
                    "async () => {"
                    "  const reg = await navigator.serviceWorker.ready;"
                    "  for (let i = 0; i < 20; i++) {"
                    "    if (reg.active && reg.active.state === 'activated') return 'activated';"
                    "    await new Promise(r => setTimeout(r, 100));"
                    "  }"
                    "  return reg.active ? reg.active.state : null;"
                    "}"
                )
                assert estado == 'activated', f'Service Worker nao ativou (estado: {estado})'
                pagina.wait_for_timeout(300)  # da tempo do 'install' terminar de cachear

                contexto.set_offline(True)
                resposta = pagina.goto(f'{servidor_django}/novo-rad/', wait_until='load')

                assert resposta is not None and resposta.ok, (
                    'A pagina /novo-rad/ nao carregou offline -- Service Worker '
                    'nao esta servindo o app shell do cache como deveria.'
                )
            finally:
                navegador.close()

    def test_cache_contem_todo_o_app_shell_esperado(self, servidor_django):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            navegador = p.chromium.launch()
            try:
                pagina = navegador.new_page()
                pagina.goto(f'{servidor_django}/entrar/')
                pagina.evaluate("async () => { await navigator.serviceWorker.ready; }")
                pagina.wait_for_timeout(300)

                caminhos_em_cache = pagina.evaluate(
                    "async () => {"
                    "  const nomes = await caches.keys();"
                    "  if (nomes.length === 0) return [];"
                    "  const cache = await caches.open(nomes[0]);"
                    "  const requests = await cache.keys();"
                    "  return requests.map(r => new URL(r.url).pathname);"
                    "}"
                )

                for caminho_esperado in (
                    '/', '/entrar/', '/inicio/', '/novo-rad/', '/consultar/',
                ):
                    assert caminho_esperado in caminhos_em_cache, (
                        f'{caminho_esperado} deveria estar no cache do app shell'
                    )
                assert any('estilo.css' in c for c in caminhos_em_cache)
                assert any('rad_form.js' in c for c in caminhos_em_cache)
            finally:
                navegador.close()

    def test_redirecionamento_de_sessao_expirada_tambem_funciona_offline(self, servidor_django):
        """
        /novo-rad/ sem sessao valida redireciona para /entrar/ via JS
        (RadAuth.exigirSessao). Confirma que essa cadeia de navegacao
        continua funcionando mesmo offline -- as duas paginas precisam
        estar no cache do Service Worker para isso funcionar.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            navegador = p.chromium.launch()
            try:
                contexto = navegador.new_context()
                pagina = contexto.new_page()
                pagina.goto(f'{servidor_django}/novo-rad/')
                pagina.evaluate("async () => { await navigator.serviceWorker.ready; }")
                pagina.wait_for_timeout(300)

                contexto.set_offline(True)
                pagina.goto(f'{servidor_django}/novo-rad/', wait_until='load')
                pagina.wait_for_timeout(300)  # tempo do redirect JS acontecer

                assert '/entrar/' in pagina.url, (
                    f'Esperava redirecionar para /entrar/ mesmo offline, ficou em {pagina.url}'
                )
            finally:
                navegador.close()
