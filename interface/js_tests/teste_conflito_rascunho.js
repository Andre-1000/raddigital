/*
 * Teste com DOM real (jsdom) do fluxo "um RAD por vez"
 * (RG-SYNC-018/019/020): ao entrar em /novo-rad/ com um rascunho ja
 * existente e com conteudo relevante, a tela deve perguntar antes de
 * mostrar o formulario -- nunca retomar nem apagar silenciosamente.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_conflito_rascunho.js <caminho_para_html_renderizado>');
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

async function montarPagina(rascunhoExistente) {
  const html = fs.readFileSync(caminhoHtml, 'utf8');
  const dom = new JSDOM(html, { url: 'http://localhost/novo-rad/', runScripts: 'outside-only' });
  const { window } = dom;
  const { document } = window;

  let limpou = false;

  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'teste.jsdom', perfis: ['usuario'] }),
    temPerfil: () => false,
    requisicaoAutenticada: async () => ({ ok: true, json: async () => ({}) }),
  };
  window.RadDB = {
    obterCatalogo: async () => [],
    obterRascunho: async () => rascunhoExistente,
    salvarRascunho: async () => {},
    limparRascunho: async () => {
      limpou = true;
    },
    dataUltimaAtualizacaoCatalogos: async () => null,
  };

  const { carregarScriptDoProjeto } = require('./carregar_script');
  const caminhoJs = path.join(__dirname, '..', 'static', 'interface', 'js');
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'regras_horario.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'validadores_arquivos.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'exportar_cliente.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'rad_form.js'));

  await new Promise((resolve) => setTimeout(resolve, 80));

  return { window, document, limpou: () => limpou };
}

async function principal() {
  // ---- Cenario 1: sem rascunho existente -- nunca pergunta ----------------

  const ctx1 = await montarPagina(null);
  assert(
    ctx1.document.getElementById('modal-conflito-rascunho').style.display === 'none' ||
      ctx1.document.getElementById('modal-conflito-rascunho').style.display === '',
    'sem rascunho existente: modal de conflito nunca aparece'
  );

  // ---- Cenario 2: rascunho existe mas esta vazio (recem-criado) -- nao pergunta ----

  const rascunhoVazio = {
    numero_os: null, numero_sa: '', servicos: [], colaboradores: [],
    amv: { id_mch: null, tipos_defeito: [], acoes: [] },
    anexos: { fotos_intervencao_verificada: [], fotos_acao_realizada: [], pdf: [] },
    sync_id_tentativa: 'x',
  };
  const ctx2 = await montarPagina(rascunhoVazio);
  assert(
    ctx2.document.getElementById('modal-conflito-rascunho').style.display !== 'flex',
    'rascunho existente mas vazio: nao pergunta (RG-SYNC-018 fala em "em preenchimento")'
  );

  // ---- Cenario 3: rascunho com conteudo relevante -- pergunta -------------

  const rascunhoComConteudo = {
    numero_os: 4321, numero_sa: '123', servicos: [], colaboradores: [],
    amv: { id_mch: null, tipos_defeito: [], acoes: [] },
    anexos: { fotos_intervencao_verificada: [], fotos_acao_realizada: [], pdf: [] },
    sync_id_tentativa: 'x',
  };
  const ctx3 = await montarPagina(rascunhoComConteudo);
  assert(
    ctx3.document.getElementById('modal-conflito-rascunho').style.display === 'flex',
    'RG-SYNC-018/019: pergunta quando ha rascunho com conteudo relevante'
  );
  assert(
    ctx3.document.getElementById('texto-conflito-rascunho').textContent.includes('4321'),
    'mensagem do conflito menciona a OS do rascunho existente'
  );
  assert(
    ctx3.document.getElementById('campo-numero-os').value === '',
    'formulario NAO fica visivel/preenchido enquanto o conflito nao e resolvido'
  );

  // "Continuar" -- resolve o conflito e mostra o formulario com os dados existentes
  ctx3.document.getElementById('botao-continuar-rascunho').dispatchEvent(
    new ctx3.window.Event('click', { bubbles: true })
  );
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert(
    ctx3.document.getElementById('modal-conflito-rascunho').style.display === 'none',
    '"Continuar" fecha o modal de conflito'
  );
  assert(
    ctx3.document.getElementById('campo-numero-os').value === '4321',
    '"Continuar" preenche o formulario com os dados do rascunho existente'
  );

  // ---- Cenario 4: "Apagar e comecar novo" -> confirmar -> cancelar -> volta ao conflito ----

  const ctx4 = await montarPagina(rascunhoComConteudo);
  ctx4.document.getElementById('botao-apagar-e-comecar-novo').dispatchEvent(
    new ctx4.window.Event('click', { bubbles: true })
  );
  assert(
    ctx4.document.getElementById('modal-confirmar-exclusao').style.display === 'flex',
    'RG-SYNC-020: "apagar e comecar novo" abre a confirmacao de irreversibilidade'
  );
  assert(
    ctx4.document.getElementById('modal-conflito-rascunho').style.display === 'none',
    'modal de conflito fecha enquanto a confirmacao de exclusao esta aberta'
  );

  ctx4.document.getElementById('botao-cancelar-exclusao').dispatchEvent(
    new ctx4.window.Event('click', { bubbles: true })
  );
  assert(
    ctx4.document.getElementById('modal-conflito-rascunho').style.display === 'flex',
    'cancelar a exclusao volta para a pergunta original, nao deixa a tela travada'
  );
  assert(!ctx4.limpou(), 'nada foi apagado ao cancelar');

  // ---- Cenario 5: "Apagar e comecar novo" -> confirmar de verdade ---------

  const ctx5 = await montarPagina(rascunhoComConteudo);
  ctx5.document.getElementById('botao-apagar-e-comecar-novo').dispatchEvent(
    new ctx5.window.Event('click', { bubbles: true })
  );
  ctx5.document.getElementById('botao-confirmar-exclusao').dispatchEvent(
    new ctx5.window.Event('click', { bubbles: true })
  );
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert(ctx5.limpou(), 'RG-SYNC-022: rascunho e removido do dispositivo ao confirmar');

  console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO INESPERADO:', erro);
  process.exit(1);
});
