"""
Consistencia entre o formulario (JS) e o servidor (Python) nas regras
de campo (30/09/2026).

O formulario avisa NA HORA quando um campo foge da regra
(interface/static/interface/js/regras_campos.js) e nao deixa enviar o
RAD enquanto isso nao for corrigido. Mas quem manda de verdade e o
servidor (rad/validadores.py). Se os dois tiverem limites diferentes,
acontece uma de duas coisas ruins:
  - o formulario e MAIS RIGIDO que o servidor: bloqueia um RAD que o
    servidor aceitaria;
  - o formulario e MENOS RIGIDO: avisa que esta tudo certo e o servidor
    recusa depois (ou, pior, estoura no banco).
Este arquivo falha se os numeros divergirem, para ninguem mudar um lado
sem lembrar do outro.
"""
import re
from pathlib import Path

from rad.validadores import (
    LIMITE_CARACTERES_RESPONSAVEL_ATIVIDADE,
    LIMITE_DIGITOS_OS,
    LIMITE_VALOR_OS,
)

RAIZ = Path(__file__).resolve().parent.parent
JS_REGRAS = RAIZ / 'interface' / 'static' / 'interface' / 'js' / 'regras_campos.js'
HTML_NOVO_RAD = RAIZ / 'interface' / 'templates' / 'interface' / 'novo_rad.html'
SERVICE_WORKER = RAIZ / 'interface' / 'service_worker_src.js'


def _constante_js(nome):
    texto = JS_REGRAS.read_text(encoding='utf-8')
    achado = re.search(rf'const {nome} = (\d+);', texto)
    assert achado, f'Nao achei "const {nome} = <numero>;" em regras_campos.js -- a constante foi renomeada?'
    return int(achado.group(1))


def test_limite_de_digitos_da_os_igual_no_formulario_e_no_servidor():
    assert _constante_js('LIMITE_DIGITOS_OS') == LIMITE_DIGITOS_OS


def test_limite_de_caracteres_do_responsavel_igual_no_formulario_e_no_servidor():
    assert _constante_js('LIMITE_CARACTERES_RESPONSAVEL') == LIMITE_CARACTERES_RESPONSAVEL_ATIVIDADE


def test_atributo_max_do_campo_os_acompanha_o_limite_do_servidor():
    html = HTML_NOVO_RAD.read_text(encoding='utf-8')
    campo = re.search(r'<input[^>]*id="campo-numero-os"[^>]*>', html)
    assert campo, 'campo-numero-os nao encontrado em novo_rad.html'
    maximo = re.search(r'max="(\d+)"', campo.group(0))
    assert maximo and int(maximo.group(1)) == LIMITE_VALOR_OS


def test_novo_rad_carrega_regras_campos_antes_do_rad_form():
    """rad_form.js usa RegrasCampos logo ao abrir -- precisa ser carregado antes."""
    html = HTML_NOVO_RAD.read_text(encoding='utf-8')
    # So as tags <script src=...> contam (o nome do arquivo tambem aparece em comentarios).
    scripts = re.findall(r'<script src="\{% static \'interface/js/([^\']+)\' %\}"></script>', html)
    assert 'regras_campos.js' in scripts, 'novo_rad.html nao carrega regras_campos.js'
    assert 'rad_form.js' in scripts
    assert scripts.index('regras_campos.js') < scripts.index('rad_form.js')


def test_service_worker_guarda_regras_campos_para_funcionar_offline():
    """
    Sem isto, o formulario abriria SEM o RegrasCampos quando o celular
    estivesse sem sinal, e o rad_form.js quebraria na primeira linha que
    o usa -- o formulario e justamente a parte que precisa funcionar offline.
    """
    assert '/static/interface/js/regras_campos.js' in SERVICE_WORKER.read_text(encoding='utf-8')
