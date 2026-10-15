/*
 * Teste com DOM real (jsdom): bloco "Inspeção e Ronda" em Servicos
 * Executados (14/10/2026).
 *
 * Carrega novo_rad.html em modo edicao com o rad_form.js VERDADEIRO e
 * confere: os blocos aparecem em ordem ALFABETICA do rotulo; o novo
 * bloco mostra "Inspeção" e "Reparo"; um servico DESATIVADO que o RAD
 * ainda usa (ex.: "Inspeção (Geral)") aparece marcado, com "(desativado)",
 * dentro do bloco Geral, e pode ser desmarcado.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_inspecao_ronda.js <caminho_para_html_renderizado>');
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

const TIPOS = [{ id: 1, nome: 'Preventiva' }, { id: 2, nome: 'Falha' }];

const base = { descricao: '', requer_amv: false, requer_descricao: false, requer_terceiros: false,
  terceiros_tem_op_maquina: false, terceiros_tem_volume: false, requer_canaleta: false };
const SERVICOS_ATIVOS = [
  { ...base, id: 1, nome: 'Soldagem', area: 'geral' },
  { ...base, id: 2, nome: 'Inspeção', area: 'insp_ronda' },
  { ...base, id: 3, nome: 'Reparo', area: 'insp_ronda' },
  { ...base, id: 4, nome: 'Inspeção AMV', area: 'amv' },
  { ...base, id: 5, nome: 'Topografia', area: 'corretiva' },
  { ...base, id: 6, nome: 'Esmerilhadora', area: 'mecanizada' },
  { ...base, id: 7, nome: 'Roçada/Poda', area: 'infra' },
];
const INSPECAO_GERAL = { ...base, id: 99, nome: 'Inspeção (Geral)', area: 'geral' };

const blocos = (document) => Array.from(document.querySelectorAll('#lista-servicos details.grupo-servicos'));
const titulo = (bloco) => bloco.querySelector('summary').textContent;
const nomesDoBloco = (bloco) => Array.from(bloco.querySelectorAll('label span')).map((s) => s.textContent);

async function montarPagina(rascunhoBase, servicosDesativados) {
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
        return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify({ rascunho: rascunhoBase, anexos: [], servicos_desativados: servicosDesativados })) };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    },
  };
  window.RadDB = {
    obterCatalogo: async (nome) => (nome === 'tipos_manutencao' ? TIPOS : nome === 'servicos' ? SERVICOS_ATIVOS : []),
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

async function principal() {
  // ---- 1. Ordem alfabetica e conteudo do bloco novo
  {
    const { document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, servicos: [1] }, []);
    const titulos = blocos(document).map(titulo);
    assert(
      JSON.stringify(titulos) === JSON.stringify(['AMV', 'Corretiva', 'Geral (1 selecionado)', 'Infra', 'Inspeção e Ronda', 'Mecanizada']),
      `blocos em ordem alfabetica (veio: ${titulos.join(' | ')})`
    );
    const ronda = blocos(document).find((b) => titulo(b).startsWith('Inspeção e Ronda'));
    assert(JSON.stringify(nomesDoBloco(ronda)) === JSON.stringify(['Inspeção', 'Reparo']), 'bloco Inspeção e Ronda tem Inspeção e Reparo');
    assert(!document.body.textContent.includes('(desativado)'), 'RAD sem servico desativado nao mostra "(desativado)"');
  }

  // ---- 2. RAD antigo com servico desativado
  {
    const { window, document } = await montarPagina({ ...RASCUNHO_DO_SERVIDOR, servicos: [99] }, [INSPECAO_GERAL]);
    const geral = blocos(document).find((b) => titulo(b).startsWith('Geral'));
    assert(titulo(geral) === 'Geral (1 selecionado)', 'bloco Geral conta o servico desativado marcado');
    const linha = Array.from(geral.querySelectorAll('label')).find((l) => l.textContent === 'Inspeção (Geral) (desativado)');
    assert(Boolean(linha), 'servico desativado aparece com "(desativado)" no bloco Geral');
    const checkbox = linha && linha.querySelector('input[type="checkbox"]');
    assert(checkbox && checkbox.checked, 'servico desativado aparece marcado');
    checkbox.checked = false;
    checkbox.dispatchEvent(new window.Event('change', { bubbles: true }));
    await esperar(20);
    assert(titulo(geral) === 'Geral', 'desmarcar o desativado atualiza o contador do bloco');
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
