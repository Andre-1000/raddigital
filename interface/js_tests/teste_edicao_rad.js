/*
 * Teste com DOM real (jsdom) do MODO EDICAO do formulario (13/10/2026).
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
  console.error('Uso: node teste_edicao_rad.js <caminho_para_html_renderizado>');
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

const ANEXOS = [
  { id: 11, tipo_arquivo: 'foto', categoria_foto: 'intervencao_verificada', categoria_foto_rotulo: 'Intervenção verificada', nome_original: 'antes.jpg', tamanho_bytes: 1000 },
  { id: 12, tipo_arquivo: 'foto', categoria_foto: 'acao_realizada', categoria_foto_rotulo: 'Ação realizada', nome_original: 'depois.jpg', tamanho_bytes: 2000 },
];

async function montarPagina(opcoes) {
  opcoes = opcoes || {};
  const html = fs.readFileSync(caminhoHtml, 'utf8');
  const dom = new JSDOM(html, { url: 'http://localhost/consultar/R00001/editar/', runScripts: 'outside-only' });
  const { window } = dom;
  const { document } = window;

  const chamadas = [];
  const efeitos = { rascunhoLido: false, rascunhoSalvo: false, rascunhoLimpo: false };

  window.RAD_EDICAO = { numero_rad: 'R00001' };
  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'admin.jsdom', perfis: ['administrador'] }),
    temPerfil: (...perfis) => (opcoes.naoAdmin ? false : perfis.includes('administrador')),
    requisicaoAutenticada: async (url, opcoesDaChamada) => {
      chamadas.push({ url, opcoes: opcoesDaChamada });
      if (url === '/configuracoes/campos/') return { ok: true, json: async () => ({ campos: [] }) };
      if (url === '/rad/R00001/dados-edicao/') {
        if (opcoes.falhaAoCarregar) {
          return { ok: false, status: 404, json: async () => ({ erro: 'RAD nao encontrado.' }) };
        }
        return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify({ rascunho: RASCUNHO_DO_SERVIDOR, anexos: ANEXOS })) };
      }
      if (url === '/rad/R00001/editar/') {
        return opcoes.respostaEditar || {
          ok: true, status: 200,
          json: async () => ({ numero_rad: 'R00001', total_alteracoes: 1, drive_desatualizado: true, planilha_desatualizada: false }),
        };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    },
  };
  window.RadDB = {
    obterCatalogo: async () => [],
    obterRascunho: async () => { efeitos.rascunhoLido = true; return null; },
    salvarRascunho: async () => { efeitos.rascunhoSalvo = true; },
    limparRascunho: async () => { efeitos.rascunhoLimpo = true; },
    dataUltimaAtualizacaoCatalogos: async () => null,
  };
  Object.defineProperty(window.navigator, 'onLine', { value: true, writable: true, configurable: true });

  const { carregarScriptDoProjeto } = require('./carregar_script');
  const caminhoJs = path.join(__dirname, '..', 'static', 'interface', 'js');
  for (const arquivo of ['regras_horario.js', 'validadores_arquivos.js', 'regras_campos.js', 'exportar_cliente.js', 'rad_form.js']) {
    carregarScriptDoProjeto(window, path.join(caminhoJs, arquivo));
  }
  await esperar(120);
  return { window, document, chamadas, efeitos };
}

const valor = (document, id) => document.getElementById(id).value;

async function principal() {
  // ---- 1. Carrega o RAD do servidor, sem tocar no rascunho do dispositivo
  {
    const { document, chamadas, efeitos } = await montarPagina();
    assert(chamadas.some((c) => c.url === '/rad/R00001/dados-edicao/'), 'busca o RAD em /rad/R00001/dados-edicao/');
    assert(efeitos.rascunhoLido === false, 'NAO le o rascunho do dispositivo (IndexedDB)');
    assert(valor(document, 'campo-numero-os') === '71000006649', 'OS de 11 digitos carregada no campo');
    assert(valor(document, 'campo-numero-sa') === '35463', 'N° SA carregado no campo');
    assert(valor(document, 'campo-observacoes-gerais') === 'obs antiga', 'Observacoes carregadas no campo');
    assert(efeitos.rascunhoSalvo === false, 'NAO grava rascunho no dispositivo ao carregar');
    assert(document.getElementById('botao-sincronizar-drive').textContent.trim() === 'Salvar alterações', 'botao principal vira "Salvar alterações"');
    const itens = document.querySelectorAll('#lista-anexos-existentes .cartao');
    assert(itens.length === 2, 'lista os 2 anexos existentes');
    assert(itens[0].textContent.includes('antes.jpg') && itens[1].textContent.includes('depois.jpg'), 'mostra o nome dos arquivos');
  }

  // ---- 2. Editar um campo NAO grava rascunho no dispositivo
  {
    const { window, document, efeitos } = await montarPagina();
    const campo = document.getElementById('campo-observacoes-gerais');
    campo.value = 'obs nova';
    campo.dispatchEvent(new window.Event('input', { bubbles: true }));
    await esperar(60);
    assert(efeitos.rascunhoSalvo === false, 'digitar no formulario nao grava rascunho no dispositivo');
  }

  // ---- 3. Motivo obrigatorio: sem motivo nao envia
  {
    const { document, chamadas } = await montarPagina();
    document.getElementById('botao-sincronizar-drive').click();
    await esperar(80);
    assert(!chamadas.some((c) => c.url === '/rad/R00001/editar/'), 'sem motivo, NAO chama o servidor');
    assert(document.getElementById('lista-erros-sincronizacao').textContent.includes('Informe o motivo da edição'), 'mostra o aviso de motivo obrigatorio');
  }

  // ---- 4. Remover foto so marca; Desfazer desmarca; envio leva motivo + ids
  {
    const { document, chamadas, efeitos } = await montarPagina();
    const botoesAlternar = () => document.querySelectorAll('#lista-anexos-existentes [data-acao="alternar"]');
    botoesAlternar()[0].click();
    assert(document.querySelectorAll('#lista-anexos-existentes .cartao')[0].textContent.includes('será removida ao salvar'), 'foto marcada mostra "sera removida ao salvar"');
    assert(botoesAlternar()[0].textContent.trim() === 'Desfazer', 'botao muda para Desfazer');
    botoesAlternar()[0].click();
    assert(!document.querySelectorAll('#lista-anexos-existentes .cartao')[0].textContent.includes('será removida'), 'Desfazer desmarca a foto');
    botoesAlternar()[1].click(); // marca a foto 12

    document.getElementById('campo-motivo-edicao').value = 'Foto errada anexada';
    document.getElementById('botao-sincronizar-drive').click();
    await esperar(150);

    const envio = chamadas.find((c) => c.url === '/rad/R00001/editar/');
    assert(!!envio, 'envia para /rad/R00001/editar/ (e nao para /rad/sincronizar/)');
    assert(!chamadas.some((c) => c.url === '/rad/sincronizar/'), 'nao chama /rad/sincronizar/');
    if (envio) {
      assert(envio.opcoes.method === 'POST', 'usa POST');
      const dados = JSON.parse(envio.opcoes.body.get('dados'));
      assert(dados.motivo_edicao === 'Foto errada anexada', 'envia o motivo');
      assert(JSON.stringify(dados.ocultar_anexos) === '[12]', 'envia so o id da foto marcada para ocultar');
      assert(dados.numero_os === 71000006649, 'envia a OS do RAD');
      assert(dados.observacoes_gerais === 'obs antiga', 'envia os demais campos como estavam');
    }
    assert(document.getElementById('aviso-sincronizacao').textContent.includes('Alterações salvas'), 'mostra confirmacao de sucesso');
    assert(document.getElementById('aviso-sincronizacao').textContent.includes('desatualizados'), 'avisa que Drive/planilha ficaram desatualizados');
    assert(efeitos.rascunhoLimpo === false, 'NAO apaga o rascunho do dispositivo');
  }

  // ---- 5. Erro 422 do servidor aparece e a pessoa continua na tela
  {
    const { document } = await montarPagina({
      respostaEditar: { ok: false, status: 422, json: async () => ({ erros: [{ codigo: 'EDT-002', mensagem: 'Nenhuma alteração foi feita no RAD.' }] }) },
    });
    document.getElementById('campo-motivo-edicao').value = 'teste';
    document.getElementById('botao-sincronizar-drive').click();
    await esperar(150);
    const erros = document.getElementById('lista-erros-sincronizacao').textContent;
    assert(erros.includes('Nenhuma alteração foi feita no RAD.'), 'mostra o erro devolvido pelo servidor');
    assert(erros.includes('salvar as alterações'), 'titulo do erro fala em salvar as alteracoes');
  }

  // ---- 6. Quem nao e Administrador nao carrega nada
  {
    const { chamadas } = await montarPagina({ naoAdmin: true });
    assert(!chamadas.some((c) => c.url === '/rad/R00001/dados-edicao/'), 'nao-admin nao busca os dados do RAD');
  }

  // ---- 7. Falha ao carregar: mensagem e formulario escondido
  {
    const { document } = await montarPagina({ falhaAoCarregar: true });
    assert(document.getElementById('aviso-formulario').textContent.includes('RAD nao encontrado.'), 'mostra o erro de carregamento');
    assert(document.getElementById('form-rad').style.display === 'none', 'esconde o formulario quando o RAD nao carregou');
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
