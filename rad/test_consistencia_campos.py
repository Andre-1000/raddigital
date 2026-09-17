"""
Teste de consistencia de campos entre o formulario (rad_form.js) e o
backend (rad/validadores.py, rad/regras_negocio.py).

Por que existe: um campo pode ser adicionado ao formulario e nunca
chegar a ser validado/persistido no backend (ou o contrario) sem que
nenhum outro teste detecte isso -- o formulario salva tudo certinho no
rascunho local (IndexedDB), o POST /rad/sincronizar/ nao quebra, mas o
valor simplesmente nunca chega ao banco nem aparece em lugar nenhum
depois. Este teste roda a cada deploy/CI e falha nesse caso, listando
exatamente quais campos ficaram "orfaos" -- em vez de depender de
alguem lembrar de checar isso manualmente toda vez que o formulario
muda.

Como funciona: le os arquivos-fonte direto do disco (Python nao roda
JS, entao isto NAO e um parser de JS de verdade) e usa expressoes
regulares para extrair:

  1. As chaves de PRIMEIRO NIVEL do objeto retornado por
     montarDadosParaEnvio() em rad_form.js -- isso e o que o
     formulario efetivamente ENVIA pro backend a cada sincronizacao.
  2. Toda chave referenciada como payload['x'] ou payload.get('x', ...)
     em rad/regras_negocio.py -- isso e o que o backend PERSISTE.
  3. O mesmo padrao em rad/validadores.py -- isso e o que o backend
     VALIDA.

Um campo enviado pelo formulario que nao aparece em NENHUM dos dois
(nem persistencia, nem validacao) e reportado como possivel campo
perdido.

Limitacoes conhecidas (por que isso NAO substitui revisao humana):
- E um regex, nao um parser real -- se alguem reescrever
  montarDadosParaEnvio() num estilo bem diferente do atual (uma chave
  por linha, "chave: valor,"), o teste pode parar de extrair
  corretamente. Nesse caso o teste falha com uma mensagem clara pedindo
  pra ajustar a extracao, em vez de passar escondendo o problema.
- So verifica a direcao formulario -> backend (campo digitado sendo
  perdido). Um campo que o backend espera mas o formulario nunca envia
  e um bug diferente (validacao vai barrar a sincronizacao direto,
  entao ja e visivel na pratica).
- So confirma que o campo E REFERENCIADO no backend -- nao confirma que
  a logica em volta dele esta correta. Isso continua sendo
  responsabilidade dos outros testes (test_regras_negocio.py,
  test_validadores.py etc).

Campos que legitimamente nao tem correspondencia direta payload['x']/
payload.get('x') no backend (ex.: campos de controle que nunca viram
coluna do Rad) vao na ALLOWLIST_CAMPOS_SEM_MATCH abaixo -- SEMPRE com
um comentario explicando o motivo, nunca em branco.
"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

CAMINHO_RAD_FORM_JS = BASE_DIR / 'interface' / 'static' / 'interface' / 'js' / 'rad_form.js'
CAMINHO_REGRAS_NEGOCIO = BASE_DIR / 'rad' / 'regras_negocio.py'
CAMINHO_VALIDADORES = BASE_DIR / 'rad' / 'validadores.py'

# Hoje (17/09/2026) esta vazia -- todo campo enviado pelo formulario
# tem correspondencia direta no backend. Se um caso legitimo aparecer
# no futuro (ex.: um campo de controle novo que nunca vira coluna do
# Rad), adicione aqui MOTIVO por que ele nao tem payload['x']/
# payload.get('x') no backend. Nunca adicione uma entrada so pra fazer
# o teste passar sem entender por que o campo esta "sumindo".
ALLOWLIST_CAMPOS_SEM_MATCH = set()


def _extrair_chaves_montar_dados_para_envio():
    """
    Extrai as chaves de PRIMEIRO NIVEL do objeto retornado por
    montarDadosParaEnvio() em rad_form.js.

    So pega chaves indentadas em exatamente 6 espacos (o nivel do
    'return {' de primeiro nivel na formatacao atual do arquivo) --
    isso evita capturar chaves de objetos aninhados dentro dela (ex.:
    'dimensao: { largura_inicial: ... }' dentro do .map() de
    canaleta_itens), que ficam mais indentados e nao sao campos que o
    backend deve ler diretamente do payload de primeiro nivel.
    """
    texto = CAMINHO_RAD_FORM_JS.read_text(encoding='utf-8')

    marcador_inicio = 'function montarDadosParaEnvio'
    marcador_fim = '\n  function renderizarErrosSincronizacao'

    assert marcador_inicio in texto, (
        f'Nao encontrei "{marcador_inicio}" em {CAMINHO_RAD_FORM_JS} -- '
        'a funcao foi renomeada ou removida? Ajuste este teste.'
    )
    inicio = texto.index(marcador_inicio)

    assert marcador_fim in texto[inicio:], (
        f'Nao encontrei o marcador de fim ("{marcador_fim.strip()}") depois de '
        f'{marcador_inicio} -- a funcao seguinte no arquivo foi renomeada? '
        'Ajuste o marcador_fim deste teste.'
    )
    fim = texto.index(marcador_fim, inicio)

    corpo = texto[inicio:fim]
    chaves = set(re.findall(r'^\s{6}([a-z_][a-z0-9_]*):', corpo, re.MULTILINE))
    return chaves


def _extrair_chaves_payload(caminho_arquivo):
    """
    Extrai toda chave referenciada como payload['x'] ou
    payload.get('x', ...) (com ou sem valor padrao) num arquivo Python
    do backend. Tambem cobre 'payload_validacao[...]'/'.get(...)', usado
    em alguns pontos de rad/regras_negocio.py.
    """
    texto = caminho_arquivo.read_text(encoding='utf-8')
    return set(
        re.findall(r"payload(?:_validacao)?(?:\.get\(|\[)'([a-z_][a-z0-9_]*)'", texto)
    )


def test_todo_campo_enviado_pelo_formulario_e_persistido_ou_validado():
    """
    Todo campo que o formulario efetivamente envia (montarDadosParaEnvio,
    em rad_form.js) precisa aparecer referenciado em
    rad/regras_negocio.py (persistencia) e/ou rad/validadores.py
    (validacao) -- senao, ou o campo esta sendo digitado e descartado
    silenciosamente na sincronizacao, ou faltou codigo no backend pra
    usa-lo.
    """
    campos_formulario = _extrair_chaves_montar_dados_para_envio()
    assert campos_formulario, (
        'Nao foi possivel extrair nenhuma chave de montarDadosParaEnvio() -- '
        'o regex pode ter parado de bater com o formato atual do arquivo '
        '(ex.: mudou a indentacao). Verifique '
        '_extrair_chaves_montar_dados_para_envio neste arquivo antes de mexer '
        'em qualquer outra coisa -- um teste que nao extrai nada nao esta '
        'testando nada.'
    )

    campos_persistidos = _extrair_chaves_payload(CAMINHO_REGRAS_NEGOCIO)
    campos_validados = _extrair_chaves_payload(CAMINHO_VALIDADORES)
    campos_conhecidos_no_backend = (
        campos_persistidos | campos_validados | ALLOWLIST_CAMPOS_SEM_MATCH
    )

    campos_orfaos = campos_formulario - campos_conhecidos_no_backend

    assert not campos_orfaos, (
        'Os campos abaixo sao enviados pelo formulario (rad_form.js, '
        'montarDadosParaEnvio) mas nao aparecem referenciados em '
        'rad/regras_negocio.py nem em rad/validadores.py -- provavel campo '
        'sendo preenchido pelo usuario e perdido na sincronizacao. Se for um '
        'caso legitimo (campo de controle que nao vira coluna do Rad), '
        'adicione a ALLOWLIST_CAMPOS_SEM_MATCH neste arquivo, com o motivo. '
        f'Campos: {sorted(campos_orfaos)}'
    )


def test_allowlist_nao_tem_entradas_obsoletas():
    """
    Espelho do teste acima: garante que ALLOWLIST_CAMPOS_SEM_MATCH nao
    acumula entradas de campos que ja nem existem mais no formulario --
    uma allowlist que so cresce e nunca encolhe vira lixo com o tempo, e
    pode acabar escondendo um campo orfao DIFERENTE que por coincidencia
    tenha o mesmo nome no futuro.
    """
    campos_formulario = _extrair_chaves_montar_dados_para_envio()
    obsoletos = ALLOWLIST_CAMPOS_SEM_MATCH - campos_formulario
    assert not obsoletos, (
        'Estes campos estao em ALLOWLIST_CAMPOS_SEM_MATCH mas nao existem '
        f'mais em montarDadosParaEnvio() -- remova-os da lista: {sorted(obsoletos)}'
    )
