/*
 * Teste com DOM real (jsdom) dos campos finais: Responsavel Atividade,
 * Operador CCM, Descricao Tecnica da Atividade, Materiais Utilizados,
 * Observacoes Gerais.
 *
 * Inclui uma checagem posicional que trava a decisao registrada em
 * docs/NOTAS_LAYOUT_FRONTEND.md: "Observacoes Gerais" deve aparecer
 * ABAIXO do bloco de anexos no HTML renderizado.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_campos_finais.js <caminho_para_html_renderizado>');
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

async function principal() {
  const html = fs.readFileSync(caminhoHtml, 'utf8');

  // ---- Checagem posicional (nao depende de JS, so da ordem no HTML) ----

  const posicaoAnexos = html.indexOf('id="miniatura-pdf"');
  const posicaoObservacoes = html.indexOf('id="campo-observacoes-gerais"');
  assert(posicaoAnexos !== -1, 'bloco de anexos (miniatura-pdf) existe no HTML');
  assert(posicaoObservacoes !== -1, 'campo Observacoes Gerais existe no HTML');
  assert(
    posicaoObservacoes > posicaoAnexos,
    'Observacoes Gerais aparece DEPOIS do bloco de anexos (docs/NOTAS_LAYOUT_FRONTEND.md)'
  );

  // ---- Interacao real com os campos ----

  const dom = new JSDOM(html, { url: 'http://localhost/novo-rad/', runScripts: 'outside-only' });
  const { window } = dom;
  const { document } = window;

  const rascunhosSalvos = [];

  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'teste.jsdom', perfis: ['usuario'] }),
    temPerfil: () => false,
    requisicaoAutenticada: async () => ({ ok: true, json: async () => ({}) }),
  };
  window.RadDB = {
    obterCatalogo: async () => [],
    obterRascunho: async () => null,
    salvarRascunho: async (login, rascunho) => {
      rascunhosSalvos.push(JSON.parse(JSON.stringify(rascunho)));
    },
    dataUltimaAtualizacaoCatalogos: async () => null,
  };

  const { carregarScriptDoProjeto } = require('./carregar_script');
  const caminhoJs = path.join(__dirname, '..', 'static', 'interface', 'js');
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'regras_horario.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'validadores_arquivos.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'exportar_cliente.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'rad_form.js'));

  await new Promise((resolve) => setTimeout(resolve, 50));

  function digitar(elementoId, valor) {
    const elemento = document.getElementById(elementoId);
    elemento.value = valor;
    elemento.dispatchEvent(new window.Event('input', { bubbles: true }));
  }

  digitar('campo-responsavel-atividade', 'Carlos Souza');
  digitar('campo-operador-ccm', 'Op. 42');
  digitar('campo-descricao-tecnica', 'Trilho com desgaste de 4,5mm — substituído.');
  digitar('campo-materiais-utilizados', 'Parafusos, graxa.');
  digitar('campo-observacoes-gerais', 'Tudo certo, sem intercorrências.');
  await new Promise((resolve) => setTimeout(resolve, 20));

  const rascunho = rascunhosSalvos[rascunhosSalvos.length - 1];
  assert(rascunho.responsavel_atividade === 'Carlos Souza', 'Responsável Atividade gravado no rascunho');
  assert(rascunho.operador_ccm === 'Op. 42', 'Operador CCM gravado no rascunho');
  assert(
    rascunho.descricao_tecnica_atividade === 'Trilho com desgaste de 4,5mm — substituído.',
    'Descrição Técnica da Atividade aceita caracteres especiais e números'
  );
  assert(rascunho.materiais_utilizados === 'Parafusos, graxa.', 'Materiais Utilizados gravado');
  assert(
    rascunho.observacoes_gerais === 'Tudo certo, sem intercorrências.',
    'Observações Gerais gravado'
  );

  console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO INESPERADO:', erro);
  process.exit(1);
});
