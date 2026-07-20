/*
 * Teste do modulo ExportarCliente (exportar_cliente.js).
 *
 * PDF (jsPDF) precisa de atob/canvas de navegador real -- testado
 * separadamente com Playwright (interface/browser_tests/). Aqui: o
 * mapeamento de campos, a mensagem de texto, a regra de habilitacao do
 * botao (RG-EXP-005), e a geracao do "Word" (HTML puro, sem
 * dependencia de biblioteca alguma, roda bem no jsdom).
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

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
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', { runScripts: 'outside-only' });
  const { window } = dom;
  const { document } = window;

  const { carregarScriptDoProjeto } = require('./carregar_script');
  carregarScriptDoProjeto(
    window,
    path.join(__dirname, '..', 'static', 'interface', 'js', 'exportar_cliente.js')
  );
  const ExportarCliente = window.ExportarCliente;

  const catalogos = {
    locais: [
      { sigla: 'BFU', nome: 'Barra Funda' },
      { sigla: 'LUZ', nome: 'Luz' },
    ],
    linhas: [{ codigo: '11', nome: 'Coral' }],
    vias: [{ id: 5, nome: 'Via 2' }],
    equipes: [{ codigo: 'VP', nome: 'VP' }, { codigo: 'SINAL', nome: 'SINAL' }],
    tipos_manutencao: [{ id: 2, nome: 'Preventiva' }],
    servicos: [{ id: 1, nome: 'Inspeção' }],
    motivos_atraso: [{ id: 3, nome: 'Trânsito' }],
    mch: [],
    colaboradores_cadastro: [],
  };

  const rascunho = {
    numero_os: 4321,
    numero_sa: '9999999999',
    data_preenchimento: '2026-07-17',
    id_local_inicial: 'BFU',
    id_local_final: 'LUZ',
    linhas: ['11'],
    vias: [5],
    equipes: ['VP', 'SINAL'],
    km_poste: '',
    id_tipo_manutencao: 2,
    numero_falha: null,
    hora_prog_inicio: '08:00',
    hora_prog_termino: '12:00',
    hora_real_inicio: '08:00',
    hora_real_termino: '12:00',
    id_motivo_atraso_inicio: null,
    desc_motivo_atraso_inicio: '',
    id_motivo_atraso_termino: null,
    desc_motivo_atraso_termino: '',
    servicos: [1],
    outros_servico_desc: '',
    materiais_utilizados: 'Parafusos',
    colaboradores: [{ nome: 'Fulano de Tal', tipo: 'colaborador', registro_empresa: '123' }],
    responsavel_atividade: 'Carlos Souza',
    operador_ccm: 'Op. 42',
    descricao_tecnica_atividade: 'Teste offline.',
    observacoes_gerais: 'Tudo certo.',
  };

  const campos = ExportarCliente.montarCampos(rascunho, catalogos);
  const mapa = Object.fromEntries(campos.map(([chave, rotulo, valor]) => [rotulo, valor]));

  assert(mapa['OS'] === '4321', 'OS aparece corretamente');
  assert(mapa['Local'] === 'BFU/LUZ', 'Local resolve sigla corretamente');
  assert(mapa['Linha'] === 'Coral', 'codigo de linha resolvido para nome via catalogo local');
  assert(mapa['Via'] === 'Via 2', 'id de via resolvido para nome via catalogo local');
  assert(mapa['Equipes Envolvidas'] === 'VP, SINAL', 'codigos de equipe resolvidos para nomes');
  assert(mapa['Atividade'] === 'Inspeção', 'id de servico resolvido para nome via catalogo local');
  assert(mapa['Responsável'] === 'Fulano de Tal', 'colaborador aparece pelo nome');
  assert(mapa['Data'] === '17/07/2026', 'data formatada em dd/mm/aaaa');
  assert(mapa['Km/Poste'] === 'N/A', 'campo vazio vira N/A');

  const camposPdf = ExportarCliente.montarCampos(rascunho, catalogos);
  assert(
    JSON.stringify(campos) === JSON.stringify(camposPdf),
    'montarCampos e deterministico -- mesma entrada, mesma saida (garante que mensagem/PDF/Word nunca divergem)'
  );

  const mensagem = ExportarCliente.gerarMensagemCopiar(rascunho, catalogos);
  assert(mensagem.startsWith('RAD - (Relatório de Atividade Diária)'), 'mensagem comeca com o cabecalho esperado');
  assert(mensagem.includes('OS: 4321'), 'mensagem contem a OS');
  assert(mensagem.includes('Responsável Atividade: Carlos Souza'), 'mensagem contem responsavel_atividade');

  assert(
    ExportarCliente.camposObrigatoriosPreenchidos(rascunho) === true,
    'RG-EXP-005: rascunho completo habilita a exportacao'
  );

  const rascunhoIncompleto = Object.assign({}, rascunho, { responsavel_atividade: '' });
  assert(
    ExportarCliente.camposObrigatoriosPreenchidos(rascunhoIncompleto) === false,
    'RG-EXP-005: falta responsavel_atividade desabilita a exportacao'
  );

  const rascunhoSemServico = Object.assign({}, rascunho, { servicos: [] });
  assert(
    ExportarCliente.camposObrigatoriosPreenchidos(rascunhoSemServico) === false,
    'RG-EXP-005: sem nenhum servico selecionado desabilita a exportacao'
  );

  const blobDocx = ExportarCliente.gerarDocxBlob(rascunho, catalogos);
  assert(blobDocx.type === 'application/msword', 'blob do Word tem o Content-Type correto');
  assert(blobDocx.size > 0, 'blob do Word nao esta vazio');

  console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO INESPERADO:', erro);
  process.exit(1);
});
