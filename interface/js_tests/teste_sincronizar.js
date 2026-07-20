/*
 * Teste com DOM real (jsdom) do bloco Sincronizar.
 *
 * O contrato do endpoint /rad/sincronizar/ em si (o que o servidor
 * aceita/valida) ja tem cobertura extensa em Python
 * (rad/test_views.py). Aqui testamos a responsabilidade do CLIENTE:
 * montar o payload certo, tratar cada resposta do servidor
 * corretamente (sucesso, erro de validacao, falha de rede) e respeitar
 * o estado offline -- por isso RadAuth.requisicaoAutenticada e
 * mockado para simular cada cenario de resposta.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_sincronizar.js <caminho_para_html_renderizado>');
  process.exit(2);
}

let falhas = 0;
function assert(condicao, mensagem) {
  if (!condicao) {
    console.error('FALHOU:', mensagem);
    falhas++;
  } else {
    console.log('OK:', mensagem);
  }
}

async function montarPagina(respostaMock) {
  const html = fs.readFileSync(caminhoHtml, 'utf8');
  const dom = new JSDOM(html, { url: 'http://localhost/novo-rad/', runScripts: 'outside-only' });
  const { window } = dom;
  const { document } = window;

  const chamadasFetch = [];
  let rascunhoLimpo = false;

  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'teste.jsdom', perfis: ['usuario'] }),
    temPerfil: () => false,
    requisicaoAutenticada: async (url, opcoes) => {
      chamadasFetch.push({ url, opcoes });
      return respostaMock;
    },
  };
  window.RadDB = {
    obterCatalogo: async () => [],
    obterRascunho: async () => null,
    salvarRascunho: async () => {},
    limparRascunho: async () => {
      rascunhoLimpo = true;
    },
    dataUltimaAtualizacaoCatalogos: async () => null,
  };

  Object.defineProperty(window.navigator, 'onLine', { value: true, writable: true, configurable: true });

  const { carregarScriptDoProjeto } = require('./carregar_script');
  const caminhoJs = path.join(__dirname, '..', 'static', 'interface', 'js');
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'regras_horario.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'validadores_arquivos.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'exportar_cliente.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'rad_form.js'));

  await new Promise((resolve) => setTimeout(resolve, 50));

  return {
    window,
    document,
    chamadasFetch,
    rascunhoLimpo: () => rascunhoLimpo,
  };
}

async function principal() {
  // ---- Cenario 1: sucesso (201) ------------------------------------------

  const ctx1 = await montarPagina({
    status: 201,
    json: async () => ({ numero_rad: 'R00001', numero_os: 1234, numero_execucao: 1, status: 'sincronizado' }),
  });
  const botao1 = ctx1.document.getElementById('botao-sincronizar');
  assert(!botao1.disabled, 'botao Sincronizar habilitado quando online e nao sincronizando');

  botao1.dispatchEvent(new ctx1.window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 30));

  assert(ctx1.chamadasFetch.length === 1, 'exatamente uma chamada de sincronizacao foi feita');
  assert(ctx1.chamadasFetch[0].url === '/rad/sincronizar/', 'URL correta chamada');
  assert(ctx1.chamadasFetch[0].opcoes.method === 'POST', 'metodo POST usado');

  const formData = ctx1.chamadasFetch[0].opcoes.body;
  const dadosEnviados = JSON.parse(formData.get('dados'));
  assert('sync_id_tentativa' in dadosEnviados, 'payload "dados" contem sync_id_tentativa');
  assert('numero_os' in dadosEnviados, 'payload "dados" contem numero_os');
  assert('colaboradores' in dadosEnviados, 'payload "dados" contem colaboradores');
  assert('amv' in dadosEnviados, 'payload "dados" contem amv');
  assert(
    !('anexos' in dadosEnviados),
    'anexos NAO vao dentro do JSON "dados" (vao como arquivos separados no FormData)'
  );

  assert(ctx1.rascunhoLimpo(), 'RG-SYNC-008/021: rascunho local limpo apos sucesso');
  assert(
    ctx1.document.getElementById('aviso-sincronizacao').textContent.includes('sucesso'),
    'mensagem de sucesso exibida'
  );

  // ---- Cenario 2: erro de validacao (422) --------------------------------

  const ctx2 = await montarPagina({
    status: 422,
    json: async () => ({
      erros: [
        { codigo: 'VLD-029', campo: 'responsavel_atividade', mensagem: 'Informe o Responsável Atividade.' },
        { codigo: 'VLD-017', campo: 'servicos', mensagem: 'Selecione ao menos um Serviço Executado.' },
      ],
    }),
  });
  const botao2 = ctx2.document.getElementById('botao-sincronizar');
  botao2.dispatchEvent(new ctx2.window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 30));

  const listaErros = ctx2.document.getElementById('lista-erros-sincronizacao');
  assert(
    listaErros.textContent.includes('Informe o Responsável Atividade.'),
    'RG-SYNC-012/017: mensagens de erro do servidor exibidas ao usuario'
  );
  assert(
    listaErros.textContent.includes('Selecione ao menos um Serviço Executado.'),
    'todos os erros retornados sao exibidos, nao so o primeiro'
  );
  assert(!ctx2.rascunhoLimpo(), 'RG-SYNC-012: rascunho NAO e apagado quando a sincronizacao falha');
  assert(!botao2.disabled, 'RG-SYNC-012: botao Sincronizar reabilitado apos falha');

  // ---- Cenario 3: falha de rede (fetch lanca excecao) --------------------

  const ctx3 = await montarPagina({ status: 201, json: async () => ({}) });
  ctx3.window.RadAuth.requisicaoAutenticada = async () => {
    throw new Error('Falha de rede simulada');
  };

  const botao3 = ctx3.document.getElementById('botao-sincronizar');
  botao3.dispatchEvent(new ctx3.window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 30));

  assert(
    ctx3.document.getElementById('lista-erros-sincronizacao').textContent.includes('conexão'),
    'RG-SYNC-012: erro de conexao exibido de forma amigavel'
  );
  assert(!ctx3.rascunhoLimpo(), 'dados preservados quando a conexao falha');
  assert(!botao3.disabled, 'botao reabilitado apos falha de rede');

  // ---- Cenario 4: offline -- botao desabilitado e clique nao faz nada ----

  const ctx4 = await montarPagina({ status: 201, json: async () => ({}) });
  Object.defineProperty(ctx4.window.navigator, 'onLine', { value: false, configurable: true });
  ctx4.window.dispatchEvent(new ctx4.window.Event('offline'));
  await new Promise((resolve) => setTimeout(resolve, 10));

  const botao4 = ctx4.document.getElementById('botao-sincronizar');
  assert(botao4.disabled, 'RG-SYNC-006/026: botao desabilitado quando offline');
  assert(
    ctx4.document.getElementById('texto-status-botao').textContent.includes('Sem conexão'),
    'indicacao "Sem conexão" exibida'
  );

  botao4.dispatchEvent(new ctx4.window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert(ctx4.chamadasFetch.length === 0, 'clique no botao desabilitado (offline) nao dispara sincronizacao');

  // ---- Cenario 5: apagar rascunho (RG-SYNC-019/020/022) ------------------

  const ctx5 = await montarPagina({ status: 201, json: async () => ({}) });
  ctx5.document.getElementById('botao-apagar-rascunho').dispatchEvent(
    new ctx5.window.Event('click', { bubbles: true })
  );
  assert(
    ctx5.document.getElementById('modal-confirmar-exclusao').style.display === 'flex',
    'modal de confirmacao aparece ao clicar em Apagar rascunho'
  );

  ctx5.document.getElementById('botao-confirmar-exclusao').dispatchEvent(
    new ctx5.window.Event('click', { bubbles: true })
  );
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert(ctx5.rascunhoLimpo(), 'confirmar exclusao chama RadDB.limparRascunho');

  console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO INESPERADO:', erro);
  process.exit(1);
});
