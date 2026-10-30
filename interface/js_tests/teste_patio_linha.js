/*
 * Teste com DOM real (jsdom), 30/10/2026: so o Pátio marcado em Via ->
 * Linha opcional, com aviso abaixo da Linha; Pátio + outra via -> Linha
 * obrigatoria. Tambem confere os rotulos "CCO" e "CCM".
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_patio_linha.js <caminho_para_html_renderizado>');
  process.exit(2);
}

let falhas = 0;
function assert(condicao, mensagem) {
  if (!condicao) { console.error('FALHOU:', mensagem); falhas++; } else { console.log('OK:', mensagem); }
}
const esperar = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const AVISO = 'Quando Pátio é selecionado, a Linha torna-se opcional';

const RASCUNHO_DO_SERVIDOR = {
  numero_os: 71000006649,
  numero_sa: '35463',
  solicitante_sa: '',
  data_preenchimento: '2026-10-01',
  data_atividade: '2026-10-01',
  id_local_inicial: 'PTR',
  id_local_final: 'PTR',
  linhas: ['11'],
  vias: [1],
  equipes: ['VP'],
  km_poste_inicial: '12/03 + 100',
  km_poste_final: '12/06 + 100',
  tipo_veiculo: '',
  operador: '',
  id_tipo_manutencao: 1,
  numero_falha: null,
  hora_prog_inicio: '08:00', data_hp_inicio: '2026-10-01',
  hora_prog_termino: '12:00', data_hp_termino: '2026-10-01',
  hora_real_inicio: '08:00', data_hr_inicio: '2026-10-01',
  hora_real_termino: '12:00', data_hr_termino: '2026-10-01',
  id_motivo_atraso_termino: null,
  desc_motivo_atraso_termino: '',
  servicos: [1],
  outros_servico_desc: '',
  desc_foto_1: '', desc_foto_2: '', desc_foto_3: '', desc_foto_4: '',
  terceiros_num_encarregados: '', terceiros_num_op_maquina: '', terceiros_num_ajudantes: '',
  terceiros_num_motorista: '', terceiros_volume: '',
  amv_blocos: [],
  canaleta_itens: [],
  colaboradores: [{ registro_empresa: null, nome: 'Participante Um', tipo: 'participante' }],
  responsavel_atividade: 'Responsavel Teste',
  operador_ccm_abertura_nome: '', operador_ccm_abertura_hora: '',
  operador_ccm_entrega_nome: '', operador_ccm_entrega_hora: '',
  descricao_tecnica_atividade: '',
  materiais_utilizados: '',
  observacoes_gerais: 'obs antiga',
  sync_id_tentativa: 'rad-original',
};

const TIPOS = [{ id: 1, nome: 'Preventiva' }];
const VIAS = [{ id: 1, nome: 'Via 1' }, { id: 2, nome: 'Via 2' }, { id: 9, nome: 'Pátio' }];
const LINHAS = [{ codigo: '11', nome: 'Coral' }];

async function montarPagina(rascunhoBase) {
  const html = fs.readFileSync(caminhoHtml, 'utf8');
  const dom = new JSDOM(html, { url: 'http://localhost/consultar/R00001/editar/', runScripts: 'outside-only' });
  const { window } = dom;
  const { document } = window;
  window.RAD_EDICAO = { numero_rad: 'R00001' };
  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'admin.jsdom', perfis: ['administrador'] }),
    temPerfil: (...perfis) => perfis.includes('administrador'),
    requisicaoAutenticada: async (url) => {
      if (url === '/configuracoes/campos/') return { ok: true, json: async () => ({ campos: [] }) };
      if (url === '/rad/R00001/dados-edicao/') {
        return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify({ rascunho: rascunhoBase, anexos: [] })) };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    },
  };
  window.RadDB = {
    obterCatalogo: async (nome) => (nome === 'tipos_manutencao' ? TIPOS : nome === 'vias' ? VIAS : nome === 'linhas' ? LINHAS : []),
    obterRascunho: async () => null,
    salvarRascunho: async () => {},
    limparRascunho: async () => {},
    dataUltimaAtualizacaoCatalogos: async () => null,
  };
  Object.defineProperty(window.navigator, 'onLine', { value: true, writable: true, configurable: true });
  const { carregarScriptDoProjeto } = require('./carregar_script');
  const caminhoJs = path.join(__dirname, '..', 'static', 'interface', 'js');
  for (const arquivo of ['regras_horario.js', 'validadores_arquivos.js', 'regras_campos.js', 'exportar_cliente.js', 'rad_form.js']) {
    carregarScriptDoProjeto(window, path.join(caminhoJs, arquivo));
  }
  await esperar(120);
  return { window, document };
}

function clicarVia(document, nome) {
  Array.from(document.querySelectorAll('#chips-vias .chip')).find((c) => c.textContent === nome).click();
}
const marcador = (document) => document.getElementById('marcador-linhas').textContent;
const aviso = (document) => document.getElementById('ajuda-linhas').textContent;

async function principal() {
  const { window, document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, vias: [1], linhas: [] });
  assert(marcador(document) === '*' && aviso(document) === '', 'Via 1: Linha obrigatoria, sem aviso');

  clicarVia(document, 'Via 1');   // desmarca Via 1
  clicarVia(document, 'Pátio');   // so Pátio
  await esperar(20);
  assert(marcador(document) === '(opcional)', 'so Pátio: Linha opcional');
  assert(aviso(document) === AVISO, 'so Pátio: aviso abaixo da Linha');

  const EC = window.ExportarCliente;
  const r = { ...RASCUNHO_DO_SERVIDOR, linhas: [], anexos: { fotos_intervencao_verificada: [{}], fotos_acao_realizada: [] } };
  assert(EC.camposObrigatoriosPreenchidos(r, false, true, true) === true, 'so Pátio: exportar liberado sem Linha');
  assert(EC.camposObrigatoriosPreenchidos(r, false, true, false) === false, 'sem Pátio: exportar exige Linha');

  clicarVia(document, 'Via 2');   // Pátio + Via 2
  await esperar(20);
  assert(marcador(document) === '*' && aviso(document) === '', 'Pátio + outra via: Linha obrigatoria de novo');

  assert(document.querySelector('.grupo-centro-operador').textContent.replace(/\s+/g, ' ').trim() === 'CCO CCM',
    'opcoes do operador sao so "CCO" e "CCM"');

  if (falhas > 0) { console.error(`\n${falhas} verificacao(oes) falharam.`); process.exit(1); }
  console.log('\nTODOS OS TESTES PASSARAM');
}

principal().catch((erro) => { console.error('Erro inesperado no teste:', erro); process.exit(1); });
