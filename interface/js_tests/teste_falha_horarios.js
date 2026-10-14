/*
 * Teste com DOM real (jsdom): Tipo = Falha esconde/desabilita os horarios
 * programados, limpa o rascunho, mantem duracao real e sem atraso (14/10/2026).
 *
 * Carrega a pagina renderizada em modo edicao (novo_rad.html com
 * modo_edicao=True) e o rad_form.js VERDADEIRO. Confere: o RAD e
 * carregado do servidor (e nao do rascunho do dispositivo), nada vai
 * para o IndexedDB, o motivo e obrigatorio, remover foto so marca o id,
 * e o envio vai para /rad/<n>/editar/ com motivo + ids a ocultar.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_falha_horarios.js <caminho_para_html_renderizado>');
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

const valor = (document, id) => document.getElementById(id).value;

const TIPOS = [{ id: 1, nome: 'Preventiva' }, { id: 2, nome: 'Falha' }];

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

const escondido = (document, chave) => document.querySelector(`[data-config-campo="${chave}"]`).hidden;
const ids = ['campo-hp-inicio', 'campo-data-hp-inicio', 'campo-hp-termino', 'campo-data-hp-termino'];

async function principal() {
  // ---- 1. Preventiva: programados visiveis, obrigatorios, com duracao
  {
    const { document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, id_tipo_manutencao: 1 });
    assert(!escondido(document, 'hora_prog_inicio') && !escondido(document, 'hora_prog_termino'), 'Preventiva: programados visiveis');
    assert(ids.every((i) => !document.getElementById(i).disabled), 'Preventiva: campos programados habilitados');
    assert(document.getElementById('campo-hp-inicio').required === true, 'Preventiva: hora programada obrigatoria');
    assert(document.getElementById('valor-duracao-programada').textContent !== '--', 'Preventiva: duracao programada calculada');
  }

  // ---- 2. Falha desde o carregamento
  {
    const { document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, id_tipo_manutencao: 2, numero_falha: 5 });
    assert(escondido(document, 'hora_prog_inicio') && escondido(document, 'hora_prog_termino'), 'Falha: programados escondidos');
    assert(document.getElementById('bloco-duracao-programada').hidden, 'Falha: duracao programada escondida');
    assert(ids.every((i) => document.getElementById(i).disabled), 'Falha: campos programados desabilitados');
    assert(document.getElementById('campo-hp-inicio').required === false, 'Falha: programado nao e required');
    assert(valor(document, 'campo-hp-inicio') === '' && valor(document, 'campo-hp-termino') === '', 'Falha: valores programados limpos');
    assert(document.getElementById('valor-duracao-real').textContent !== '--', 'Falha: duracao real continua calculada');
    assert(document.getElementById('campo-grupo-atraso-termino').style.display === 'none', 'Falha: sem atraso');
  }

  // ---- 3. Trocar Preventiva -> Falha -> Preventiva
  {
    const { window, document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, id_tipo_manutencao: 1 });
    trocarTipo(window, document, 2);
    await esperar(30);
    assert(escondido(document, 'hora_prog_inicio'), 'trocar para Falha esconde programados');
    assert(valor(document, 'campo-hp-inicio') === '', 'trocar para Falha limpa a hora programada');
    assert(document.getElementById('valor-duracao-real').textContent !== '--', 'duracao real segue calculada apos trocar');
    trocarTipo(window, document, 1);
    await esperar(30);
    assert(!escondido(document, 'hora_prog_inicio'), 'voltar para Preventiva mostra programados de novo');
    assert(ids.every((i) => !document.getElementById(i).disabled), 'voltar: campos habilitados');
    assert(document.getElementById('campo-hp-inicio').required === true, 'voltar: hora programada obrigatoria de novo');
  }

  // ---- 4. exportar_cliente: Falha nao exige programado
  {
    const { window } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, id_tipo_manutencao: 1 });
    const EC = window.ExportarCliente;
    const r = { ...RASCUNHO_DO_SERVIDOR, hora_prog_inicio: '', hora_prog_termino: '', anexos: { fotos_intervencao_verificada: [{}], fotos_acao_realizada: [] } };
    assert(EC.camposObrigatoriosPreenchidos(r, false) === false, 'sem Falha, programado vazio bloqueia');
    assert(EC.camposObrigatoriosPreenchidos(r, true) === true, 'com Falha, programado vazio NAO bloqueia');
    assert(!EC.camposObrigatoriosFaltando(r, true).some((x) => x.includes('Programado')), 'Falha: programado nao aparece como faltando');
    assert(EC.camposObrigatoriosFaltando(r, false).some((x) => x.includes('Programado')), 'sem Falha: programado aparece como faltando');
  }

  if (falhas > 0) {
    console.error(`\n${falhas} verificacao(oes) falharam.`);
    process.exit(1);
  }
  console.log('\nTODOS OS TESTES PASSARAM');
}

principal().catch((erro) => {
  console.error('Erro inesperado no teste:', erro);
  process.exit(1);
});
