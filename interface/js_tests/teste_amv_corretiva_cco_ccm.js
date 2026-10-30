/*
 * Teste com DOM real (jsdom), 30/10/2026:
 *  - "Manutenção Corretiva em AMV" (bloco Corretiva) abre o Bloco AMV com
 *    no maximo 3 blocos; "Manutenção em AMV" continua com 16; os dois
 *    marcados = 16; acima do limite avisa sem apagar nada;
 *  - Operador CCO/CCM: marcar CCO desmarca CCM (e vice-versa), pode ficar
 *    vazio, a Entrega copia a Abertura ate ser mexida, e vai no envio.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_amv_corretiva_cco_ccm.js <caminho_para_html_renderizado>');
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

const TIPOS = [{ id: 1, nome: 'Preventiva' }, { id: 2, nome: 'Falha' }, { id: 3, nome: 'Corretiva' }];
const base = { descricao: '', requer_descricao: false, requer_terceiros: false, terceiros_tem_op_maquina: false,
  terceiros_tem_volume: false, requer_canaleta: false };
const SERVICOS = [
  { ...base, id: 1, nome: 'Soldagem', area: 'geral', requer_amv: false, limite_blocos_amv: null },
  { ...base, id: 10, nome: 'Manutenção em AMV', area: 'amv', requer_amv: true, limite_blocos_amv: null },
  { ...base, id: 11, nome: 'Manutenção Corretiva em AMV', area: 'corretiva', requer_amv: true, limite_blocos_amv: 3 },
];

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
    obterCatalogo: async (nome) => (nome === 'tipos_manutencao' ? TIPOS : nome === 'servicos' ? SERVICOS : []),
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

function marcarServico(window, document, id, marcado) {
  const caixa = Array.from(document.querySelectorAll('#lista-servicos input[type="checkbox"]'))
    .find((c) => c.closest('label').textContent.trim().startsWith(SERVICOS.find((s) => s.id === id).nome));
  caixa.checked = marcado;
  caixa.dispatchEvent(new window.Event('change', { bubbles: true }));
}
const contador = (document) => document.getElementById('contador-blocos-amv').textContent;
const botaoMch = (document) => document.getElementById('botao-adicionar-mch');
const blocos = (document) => document.querySelectorAll('#container-blocos-amv .bloco-amv').length;

async function principal() {
  // ---- 1. Corretiva em AMV: no bloco Corretiva, limite 3
  {
    const { window, document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, servicos: [1] });
    const corretiva = Array.from(document.querySelectorAll('#lista-servicos details.grupo-servicos'))
      .find((d) => d.querySelector('summary').textContent.startsWith('Corretiva'));
    assert(Boolean(corretiva) && corretiva.textContent.includes('Manutenção Corretiva em AMV'), 'servico aparece no bloco Corretiva');
    marcarServico(window, document, 11, true);
    await esperar(20);
    assert(document.getElementById('bloco-amv').style.display !== 'none', 'Corretiva em AMV abre o Bloco AMV');
    assert(contador(document) === '1 de 3 blocos usados', `contador comeca em 1 de 3 (veio: ${contador(document)})`);
    botaoMch(document).click(); botaoMch(document).click();
    await esperar(20);
    assert(blocos(document) === 3, '1 inicial + 2 pelo botao = 3 blocos');
    assert(botaoMch(document).style.display === 'none', 'botao "Adicionar MCH" some no 3o bloco');
    botaoMch(document).click();
    await esperar(20);
    assert(blocos(document) === 3, 'nao passa de 3 blocos');
    // ---- os dois servicos marcados: vale 16
    marcarServico(window, document, 10, true);
    await esperar(20);
    assert(contador(document) === '3 de 16 blocos usados', `com os dois servicos vale 16 (veio: ${contador(document)})`);
    assert(botaoMch(document).style.display !== 'none', 'botao volta a aparecer');
    botaoMch(document).click();
    await esperar(20);
    assert(blocos(document) === 4, 'adiciona o 4o bloco com o limite 16');
    // ---- desmarca o de 16: 4 blocos > 3 -> aviso, nada apagado
    marcarServico(window, document, 10, false);
    await esperar(20);
    assert(blocos(document) === 4, 'acima do limite: nenhum bloco e apagado sozinho');
    assert(contador(document).includes('remova 1'), `acima do limite: aviso para remover (veio: ${contador(document)})`);
  }

  // ---- 2. Operador CCO/CCM
  {
    const { window, document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR });
    const c = (qual, centro) => document.getElementById(`campo-operador-ccm-${qual}-${centro}`);
    const clicar = (el) => { el.checked = !el.checked; el.dispatchEvent(new window.Event('change', { bubbles: true })); };
    assert(!c('abertura', 'cco').checked && !c('abertura', 'ccm').checked, 'comeca sem escolha (opcional)');
    clicar(c('abertura', 'cco'));
    assert(c('abertura', 'cco').checked && !c('abertura', 'ccm').checked, 'marcar CCO na Abertura');
    assert(c('entrega', 'cco').checked, 'Entrega copia a Abertura');
    clicar(c('abertura', 'ccm'));
    assert(!c('abertura', 'cco').checked && c('abertura', 'ccm').checked, 'marcar CCM desmarca CCO');
    assert(c('entrega', 'ccm').checked && !c('entrega', 'cco').checked, 'Entrega acompanha a troca');
    clicar(c('entrega', 'cco'));
    assert(c('entrega', 'cco').checked && !c('entrega', 'ccm').checked, 'Entrega pode ser trocada a mao');
    clicar(c('abertura', 'ccm'));
    assert(!c('abertura', 'ccm').checked && !c('abertura', 'cco').checked, 'desmarcar deixa a Abertura vazia');
    assert(c('entrega', 'cco').checked, 'depois de mexida, a Entrega nao e mais sobrescrita');
  }

  // ---- 3. Edicao de RAD salvo: mostra o que estava gravado
  {
    const { document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, operador_ccm_abertura_centro: 'CCM', operador_ccm_entrega_centro: 'CCO' });
    assert(document.getElementById('campo-operador-ccm-abertura-ccm').checked, 'edicao: Abertura CCM marcada');
    assert(document.getElementById('campo-operador-ccm-entrega-cco').checked, 'edicao: Entrega CCO marcada');
  }

  if (falhas > 0) { console.error(`\n${falhas} verificacao(oes) falharam.`); process.exit(1); }
  console.log('\nTODOS OS TESTES PASSARAM');
}

principal().catch((erro) => { console.error('Erro inesperado no teste:', erro); process.exit(1); });
