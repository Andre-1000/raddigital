/*
 * Teste com DOM real (jsdom) do bloco Colaboradores e Participantes.
 *
 * Mesmo padrao de interface/js_tests/teste_bloco_amv.js: HTML
 * renderizado de verdade pelo Django, RadAuth/RadDB mockados, cliques
 * simulados de verdade.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_colaboradores.js <caminho_para_html_renderizado>');
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

  const rascunhosSalvos = [];

  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'teste.jsdom', perfis: ['usuario'] }),
    temPerfil: () => false,
    requisicaoAutenticada: async () => ({ ok: true, json: async () => ({}) }),
  };

  const catalogoColaboradores = [
    { registro_empresa: '12345', nome: 'Carlos Souza' },
    { registro_empresa: '67890', nome: 'Marcia Lima' },
  ];

  const catalogosPorNome = {
    locais: [], linhas: [], vias: [], equipes: [], tipos_manutencao: [],
    motivos_atraso: [], servicos: [], mch: [], tipos_defeito_amv: [], acoes_amv: [],
    colaboradores_cadastro: catalogoColaboradores,
  };

  window.RadDB = {
    obterCatalogo: async (nome) => catalogosPorNome[nome] || [],
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

  function ultimoRascunho() {
    return rascunhosSalvos[rascunhosSalvos.length - 1];
  }

  // ---- Adicionar colaborador via busca ----

  const botaoAdicionarColaborador = document.getElementById('botao-adicionar-colaborador');
  botaoAdicionarColaborador.dispatchEvent(new window.Event('click', { bubbles: true }));

  const campoBusca = document.getElementById('campo-busca-colaborador');
  assert(
    document.getElementById('bloco-busca-colaborador').style.display !== 'none',
    'bloco de busca aparece ao clicar em Adicionar Colaborador'
  );

  campoBusca.value = '123';
  campoBusca.dispatchEvent(new window.Event('input', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  const resultados = document.getElementById('resultados-busca-colaborador');
  const botaoResultado = resultados.querySelector('button');
  assert(
    botaoResultado !== null && botaoResultado.textContent.includes('Carlos Souza'),
    'busca por "123" encontra Carlos Souza (registro 12345)'
  );

  botaoResultado.dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  assert(
    ultimoRascunho().colaboradores.some(
      (p) => p.registro_empresa === '12345' && p.nome === 'Carlos Souza' && p.tipo === 'colaborador'
    ),
    'colaborador adicionado ao rascunho com nome vindo do cadastro (RG-RESP-004/005)'
  );

  // ---- RG-RESP-008: busca sem resultado ----

  botaoAdicionarColaborador.dispatchEvent(new window.Event('click', { bubbles: true }));
  const campoBusca2 = document.getElementById('campo-busca-colaborador');
  campoBusca2.value = 'ninguem-com-esse-nome-existe';
  campoBusca2.dispatchEvent(new window.Event('input', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  const resultadosVazio = document.getElementById('resultados-busca-colaborador');
  assert(
    resultadosVazio.textContent.includes('Colaborador não localizado.'),
    'RG-RESP-008: mensagem exata exibida quando ninguem e encontrado'
  );

  // ---- RG-RESP-009: nao permite adicionar o mesmo registro duas vezes ----

  botaoAdicionarColaborador.dispatchEvent(new window.Event('click', { bubbles: true }));
  const campoBusca3 = document.getElementById('campo-busca-colaborador');
  campoBusca3.value = '12345';
  campoBusca3.dispatchEvent(new window.Event('input', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  const botaoDuplicado = document.getElementById('resultados-busca-colaborador').querySelector('button');
  botaoDuplicado.dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  const quantidadeComRegistro12345 = ultimoRascunho().colaboradores.filter(
    (p) => p.registro_empresa === '12345'
  ).length;
  assert(
    quantidadeComRegistro12345 === 1,
    'RG-RESP-009: nao duplica o mesmo registro (continua com exatamente 1)'
  );
  assert(
    document.getElementById('aviso-colaboradores').textContent.includes('já foi adicionado'),
    'aviso de duplicidade exibido ao usuario'
  );

  // ---- Adicionar participante externo ----

  document.getElementById('botao-adicionar-participante').dispatchEvent(
    new window.Event('click', { bubbles: true })
  );
  const campoNomeParticipante = document.getElementById('campo-nome-participante');
  campoNomeParticipante.value = 'Visitante da Prefeitura';
  document.getElementById('botao-confirmar-participante').dispatchEvent(
    new window.Event('click', { bubbles: true })
  );
  await new Promise((resolve) => setTimeout(resolve, 10));

  assert(
    ultimoRascunho().colaboradores.some(
      (p) => p.tipo === 'participante' && p.nome === 'Visitante da Prefeitura' && p.registro_empresa === null
    ),
    'participante externo adicionado sem registro_empresa (RG-RESP-013/014)'
  );

  // ---- Remover ----

  const totalAntes = ultimoRascunho().colaboradores.length;
  const botoesRemover = document.querySelectorAll('#lista-colaboradores-adicionados button');
  assert(botoesRemover.length === totalAntes, `existem ${totalAntes} botoes de remover na lista`);
  botoesRemover[0].dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 10));

  assert(
    ultimoRascunho().colaboradores.length === totalAntes - 1,
    'RG-RESP-007: remover antes da sincronizacao funciona'
  );

  console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO INESPERADO:', erro);
  process.exit(1);
});
