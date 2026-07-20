/*
 * Teste com DOM real (jsdom) do bloco Servicos + AMV.
 *
 * Carrega o HTML de verdade renderizado pelo Django (passado como
 * argumento, gerado a cada execucao pelo teste Python que chama este
 * script -- nunca fica desatualizado em relacao ao template real),
 * simula RadAuth/RadDB (que dependem de localStorage/IndexedDB, nao
 * disponiveis puros no jsdom), injeta catalogos falsos e simula
 * cliques de verdade nos checkboxes.
 *
 * Existe para travar um bug real que foi pego durante o
 * desenvolvimento: os checkboxes de Tipo de Defeito/Acoes perdiam a
 * ligacao com rascunho.amv quando o bloco AMV era escondido e
 * mostrado de novo, porque o array era substituido em vez de mutado
 * in-place. Este teste reproduz exatamente esse cenario.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_bloco_amv.js <caminho_para_html_renderizado>');
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
  const dom = new JSDOM(html, { url: 'http://localhost/novo-rad/', runScripts: 'outside-only' });
  const { window } = dom;
  const { document } = window;

  // ---- Mocks de RadAuth e RadDB (dependem de localStorage/IndexedDB) ----

  const rascunhosSalvos = [];

  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'teste.jsdom', perfis: ['usuario'] }),
    temPerfil: () => false,
    requisicaoAutenticada: async () => ({ ok: true, json: async () => ({}) }),
  };

  const catalogoServicos = [
    { id: 1, nome: 'Inspecao', descricao: 'Verificacao visual.', requer_amv: false, requer_descricao: false },
    { id: 2, nome: 'Manutencao em AMV', descricao: 'Abre o bloco AMV.', requer_amv: true, requer_descricao: false },
    { id: 3, nome: 'Outros', descricao: 'Servico nao listado.', requer_amv: false, requer_descricao: true },
  ];
  const catalogoMch = [
    { id: 10, identificacao: 'MCH01A-BFU', modelo: 'M23-E', via: '3', ur: 'BFU', local_amv: 'BFU', linha: '11' },
  ];
  const catalogoTiposDefeito = [
    { id: 100, nome: 'DESGASTE' },
    { id: 101, nome: 'MAU CONTATO' },
  ];
  const catalogoAcoes = [
    { id: 200, nome: 'LUBRIFICACAO' },
    { id: 201, nome: 'ALINHAMENTO' },
  ];

  const catalogosPorNome = {
    locais: [], linhas: [], vias: [], equipes: [], tipos_manutencao: [],
    motivos_atraso: [],
    servicos: catalogoServicos,
    mch: catalogoMch,
    tipos_defeito_amv: catalogoTiposDefeito,
    acoes_amv: catalogoAcoes,
  };

  window.RadDB = {
    obterCatalogo: async (nome) => catalogosPorNome[nome] || [],
    obterRascunho: async () => null, // sempre comeca um rascunho novo neste teste
    salvarRascunho: async (login, rascunho) => {
      rascunhosSalvos.push(JSON.parse(JSON.stringify(rascunho)));
    },
    dataUltimaAtualizacaoCatalogos: async () => null,
  };

  // ---- Carrega os scripts reais do projeto (mesmo codigo que roda no navegador) ----

  const { carregarScriptDoProjeto } = require('./carregar_script');
  const caminhoJs = path.join(__dirname, '..', 'static', 'interface', 'js');
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'regras_horario.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'validadores_arquivos.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'exportar_cliente.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'rad_form.js'));

  // Dispara DOMContentLoaded manualmente (jsdom com runScripts:
  // 'outside-only' nao executa <script src> automaticamente, entao o
  // listener foi registrado pelo eval acima; agora disparamos o evento).

  // Espera as Promises internas (varios awaits em cadeia) resolverem.
  await new Promise((resolve) => setTimeout(resolve, 50));

  // ---- Simulacao: marcar "Manutencao em AMV" ----

  function encontrarCheckboxPorRotulo(container, rotulo) {
    const labels = container.querySelectorAll('label');
    for (const label of labels) {
      if (label.textContent.includes(rotulo)) {
        return label.querySelector('input[type="checkbox"]');
      }
    }
    return null;
  }

  const listaServicos = document.getElementById('lista-servicos');
  const checkboxAmv = encontrarCheckboxPorRotulo(listaServicos, 'Manutencao em AMV');
  assert(checkboxAmv !== null, 'checkbox do servico "Manutencao em AMV" encontrado');

  checkboxAmv.checked = true;
  checkboxAmv.dispatchEvent(new window.Event('change', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  const blocoAmv = document.getElementById('bloco-amv');
  assert(blocoAmv.style.display !== 'none', 'bloco AMV aparece ao marcar o servico');

  // Marca um tipo de defeito
  const listaTiposDefeito = document.getElementById('lista-tipos-defeito');
  const checkboxDesgaste = encontrarCheckboxPorRotulo(listaTiposDefeito, 'DESGASTE');
  assert(checkboxDesgaste !== null, 'checkbox "DESGASTE" encontrado no bloco AMV');
  checkboxDesgaste.checked = true;
  checkboxDesgaste.dispatchEvent(new window.Event('change', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  let ultimoRascunho = rascunhosSalvos[rascunhosSalvos.length - 1];
  assert(
    ultimoRascunho.amv.tipos_defeito.includes(100),
    'marcar DESGASTE grava o id 100 em rascunho.amv.tipos_defeito'
  );

  // ---- O cenario do bug: desmarcar e remarcar o servico AMV ----

  checkboxAmv.checked = false;
  checkboxAmv.dispatchEvent(new window.Event('change', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  ultimoRascunho = rascunhosSalvos[rascunhosSalvos.length - 1];
  assert(
    ultimoRascunho.amv.tipos_defeito.length === 0,
    'desmarcar o servico AMV limpa tipos_defeito'
  );

  checkboxAmv.checked = true;
  checkboxAmv.dispatchEvent(new window.Event('change', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  // Re-marca um tipo de defeito DEPOIS do ciclo esconder/mostrar --
  // este e o passo que reproduzia o bug original (array desconectado).
  const listaTiposDefeitoDepois = document.getElementById('lista-tipos-defeito');
  const checkboxMauContato = encontrarCheckboxPorRotulo(listaTiposDefeitoDepois, 'MAU CONTATO');
  assert(checkboxMauContato !== null, 'checkbox "MAU CONTATO" existe apos re-render do bloco AMV');
  checkboxMauContato.checked = true;
  checkboxMauContato.dispatchEvent(new window.Event('change', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  ultimoRascunho = rascunhosSalvos[rascunhosSalvos.length - 1];
  assert(
    ultimoRascunho.amv.tipos_defeito.includes(101),
    'apos esconder/mostrar o bloco AMV, marcar MAU CONTATO ainda grava no rascunho (regressao do bug de closure)'
  );

  console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO INESPERADO:', erro);
  process.exit(1);
});
