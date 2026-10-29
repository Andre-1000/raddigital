/*
 * Teste com DOM real (jsdom): OS e N° SA com regra fixa (29/10/2026).
 * Carrega novo_rad.html (modo edicao) com o rad_form.js VERDADEIRO e
 * confere: Controle Operacional vem antes de Identificacao; Falha
 * desativa e limpa N° SA e Solicitante SA; Preventiva/Preditiva marcam
 * a SA como obrigatoria; Corretiva como opcional; e a exportacao so
 * exige SA quando o tipo pede.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_os_sa_regra_fixa.js <caminho_para_html_renderizado>');
  process.exit(2);
}

let falhas = 0;
function assert(condicao, mensagem) {
  if (!condicao) { console.error('FALHOU:', mensagem); falhas++; } else { console.log('OK:', mensagem); }
}
const esperar = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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

const TIPOS = [{ id: 1, nome: 'Preventiva' }, { id: 2, nome: 'Falha' }, { id: 3, nome: 'Corretiva' }, { id: 4, nome: 'Preditiva' }];

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
    obterCatalogo: async (nome) => (nome === 'tipos_manutencao' ? TIPOS : []),
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

function trocarTipo(window, document, id) {
  const sel = document.getElementById('campo-tipo-manutencao');
  sel.value = String(id);
  sel.dispatchEvent(new window.Event('change', { bubbles: true }));
}

const sa = (document) => document.getElementById('campo-numero-sa');
const solicitante = (document) => document.getElementById('campo-solicitante-sa');
const marcador = (document) => document.getElementById('marcador-numero_sa').textContent;

async function principal() {
  // ---- 1. Ordem dos blocos
  {
    const { document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, id_tipo_manutencao: 1 });
    const secoes = Array.from(document.querySelectorAll('.cartao[id^="secao-"]')).map((el) => el.id);
    assert(secoes.indexOf('secao-controle-operacional') < secoes.indexOf('secao-identificacao'),
      'Controle Operacional vem antes de Identificacao');
    assert(secoes.indexOf('secao-identificacao') < secoes.indexOf('secao-localizacao'),
      'Identificacao continua antes de Localizacao');
    const atalhos = Array.from(document.querySelectorAll('.nav-lateral-formulario a[href^="#secao-"]')).map((a) => a.getAttribute('href'));
    assert(atalhos[0] === '#secao-controle-operacional', 'atalho lateral tambem comeca por Controle Operacional');
  }

  // ---- 2. Preventiva: SA obrigatoria
  {
    const { document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, id_tipo_manutencao: 1, numero_sa: '35463', solicitante_sa: 'Fulano' });
    assert(!sa(document).disabled && !solicitante(document).disabled, 'Preventiva: SA e Solicitante ativos');
    assert(marcador(document) === '*', 'Preventiva: SA marcada como obrigatoria');
    assert(sa(document).value === '35463', 'Preventiva: SA preservada');
  }

  // ---- 3. Trocar para Falha: desativa e limpa
  {
    const { window, document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, id_tipo_manutencao: 1, numero_sa: '35463', solicitante_sa: 'Fulano' });
    trocarTipo(window, document, 2);
    await esperar(30);
    assert(sa(document).disabled && solicitante(document).disabled, 'Falha: SA e Solicitante desativados');
    assert(sa(document).value === '' && solicitante(document).value === '', 'Falha: SA e Solicitante limpos');
    assert(!document.getElementById('ajuda-numero-sa').hidden, 'Falha: aviso "nao se aplica" visivel');
    assert(marcador(document) === '', 'Falha: sem marcador de obrigatorio');
    // ---- e voltar para Corretiva: reativa, opcional
    trocarTipo(window, document, 3);
    await esperar(30);
    assert(!sa(document).disabled && !solicitante(document).disabled, 'Corretiva: SA e Solicitante reativados');
    assert(marcador(document) === '(opcional)', 'Corretiva: SA opcional');
    assert(document.getElementById('ajuda-numero-sa').hidden, 'Corretiva: aviso escondido');
    trocarTipo(window, document, 4);
    await esperar(30);
    assert(marcador(document) === '*', 'Preditiva: SA obrigatoria');
  }

  // ---- 4. Exportacao: SA so e exigida quando o tipo pede
  {
    const { window } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, id_tipo_manutencao: 1 });
    const EC = window.ExportarCliente;
    const r = { ...RASCUNHO_DO_SERVIDOR, numero_sa: '', anexos: { fotos_intervencao_verificada: [{}], fotos_acao_realizada: [] } };
    assert(EC.camposObrigatoriosPreenchidos(r, false, true) === false, 'Preventiva sem SA bloqueia a exportacao');
    assert(EC.camposObrigatoriosPreenchidos(r, false, false) === true, 'Corretiva sem SA libera a exportacao');
    assert(EC.camposObrigatoriosFaltando(r, false, true).includes('N° SA'), 'Preventiva: SA aparece como faltando');
    assert(!EC.camposObrigatoriosFaltando(r, false, false).includes('N° SA'), 'Corretiva: SA nao aparece como faltando');
  }

  if (falhas > 0) { console.error(`\n${falhas} verificacao(oes) falharam.`); process.exit(1); }
  console.log('\nTODOS OS TESTES PASSARAM');
}

principal().catch((erro) => { console.error('Erro inesperado no teste:', erro); process.exit(1); });
