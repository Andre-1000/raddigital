/*
 * Teste com DOM real (jsdom): filtro "Serviço executado" da Consulta
 * lista tambem servicos DESATIVADOS (15/10/2026).
 *
 * Carrega consulta.html renderizado (script inline verdadeiro) e
 * confere: o catalogo e pedido com ?incluir_servicos_desativados=1;
 * ao escolher a Area Geral, a Subcategoria mostra o desativado com
 * "(desativado)", depois dos ativos; marcar ele manda servico_ids na
 * pesquisa; nome com HTML e escapado.
 */
const fs = require('fs');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_consulta_servico_desativado.js <caminho_para_html_renderizado>');
  process.exit(2);
}

let falhas = 0;
function assert(condicao, mensagem) {
  if (!condicao) { console.error('FALHOU:', mensagem); falhas++; } else { console.log('OK:', mensagem); }
}
const esperar = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const CATALOGOS = {
  locais: [], tipos_manutencao: [], mch: [], linhas: [],
  servicos: [
    { id: 1, nome: 'Soldagem', area: 'geral' },
    { id: 2, nome: 'Alinhamento', area: 'geral' },
    { id: 3, nome: 'Inspeção', area: 'insp_ronda' },
  ],
  servicos_desativados: [
    { id: 90, nome: 'Inspeção (Geral)', area: 'geral' },
    { id: 91, nome: '<img src=x onerror=alert(1)>', area: 'geral' },
  ],
};

async function principal() {
  const html = fs.readFileSync(caminhoHtml, 'utf8');
  const dom = new JSDOM(html, { url: 'http://localhost/consultar/', runScripts: 'dangerously' });
  const { window } = dom;
  const { document } = window;
  const urls = [];
  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'admin.jsdom', perfis: ['administrador'] }),
    temPerfil: () => true,
    sair: () => {},
    requisicaoAutenticada: async (url) => {
      urls.push(url);
      if (url.startsWith('/catalogos/todos/')) return { ok: true, json: async () => CATALOGOS };
      if (url.startsWith('/colaboradores/todos/')) return { ok: true, json: async () => ({ colaboradores: [] }) };
      if (url.startsWith('/consulta/rads/')) return { ok: true, json: async () => ({ resultados: [], total: 0, pagina: 1, total_paginas: 1 }) };
      return { ok: false, status: 404, json: async () => ({}) };
    },
  };
  document.dispatchEvent(new window.Event('DOMContentLoaded'));
  await esperar(100);

  assert(urls.includes('/catalogos/todos/?incluir_servicos_desativados=1'), 'catalogo pedido com desativados');

  const area = document.getElementById('filtro-servico-area');
  area.value = 'geral';
  area.dispatchEvent(new window.Event('change'));
  const rotulos = Array.from(document.querySelectorAll('#lista-subcategoria-servico label')).map((l) => l.textContent.trim());
  assert(
    JSON.stringify(rotulos) === JSON.stringify(['Alinhamento', 'Soldagem', '<img src=x onerror=alert(1)> (desativado)', 'Inspeção (Geral) (desativado)']),
    `ativos primeiro, desativados no fim com "(desativado)" (veio: ${rotulos.join(' | ')})`
  );
  assert(document.querySelector('#lista-subcategoria-servico img') === null, 'nome de servico e escapado (sem HTML injetado)');

  area.value = 'insp_ronda';
  area.dispatchEvent(new window.Event('change'));
  const ronda = Array.from(document.querySelectorAll('#lista-subcategoria-servico label')).map((l) => l.textContent.trim());
  assert(JSON.stringify(ronda) === JSON.stringify(['Inspeção']), 'Inspeção e Ronda nao recebe desativados do Geral');

  area.value = 'geral';
  area.dispatchEvent(new window.Event('change'));
  document.querySelector('.checkbox-subcategoria-servico[value="90"]').checked = true;
  const botao = Array.from(document.querySelectorAll('button')).find((b) => /Pesquisar/i.test(b.textContent));
  botao.click();
  await esperar(50);
  const pesquisa = urls.find((u) => u.startsWith('/consulta/rads/?'));
  assert(Boolean(pesquisa) && new URLSearchParams(pesquisa.split('?')[1]).get('servico_ids') === '90', `pesquisa envia servico_ids=90 (veio: ${pesquisa})`);

  if (falhas > 0) { console.error(`\n${falhas} verificacao(oes) falharam.`); process.exit(1); }
  console.log('\nTODOS OS TESTES PASSARAM');
}

principal().catch((erro) => { console.error('Erro inesperado no teste:', erro); process.exit(1); });
