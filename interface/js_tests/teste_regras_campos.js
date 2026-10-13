/*
 * Teste com DOM real (jsdom) dos AVISOS DE REGRA POR CAMPO (30/09/2026).
 *
 * Carrega a pagina de Novo RAD renderizada pelo Django e o
 * rad_form.js VERDADEIRO (alem de regras_campos.js), digita nos campos
 * e confere: o aviso aparece abaixo do campo, some quando o valor e
 * corrigido, e a sincronizacao NAO e enviada enquanto houver um campo
 * visivel fora da regra.
 *
 * Autocontido de proposito: nao depende dos outros testes jsdom (varios
 * estao desatualizados em relacao ao formulario de hoje).
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_regras_campos.js <caminho_para_html_renderizado>');
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

async function montarPagina(opcoes) {
  const respostaConfiguracoes = (opcoes && opcoes.respostaConfiguracoes) || {
    ok: true,
    json: async () => ({ campos: [] }),
  };

  const html = fs.readFileSync(caminhoHtml, 'utf8');
  const dom = new JSDOM(html, { url: 'http://localhost/novo-rad/', runScripts: 'outside-only' });
  const { window } = dom;
  const { document } = window;

  const chamadas = [];

  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'teste.jsdom', perfis: ['usuario'] }),
    temPerfil: () => false,
    requisicaoAutenticada: async (url, opcoesDaChamada) => {
      chamadas.push({ url, opcoes: opcoesDaChamada });
      if (url === '/configuracoes/campos/') return respostaConfiguracoes;
      // Qualquer outra chamada (sincronizar): resposta de validacao do
      // servidor -- o que interessa aqui e SE a chamada foi feita.
      return { status: 422, json: async () => ({ erros: [{ mensagem: 'recusado pelo servidor (mock)' }] }) };
    },
  };
  window.RadDB = {
    obterCatalogo: async () => [],
    obterRascunho: async () => null,
    salvarRascunho: async () => {},
    limparRascunho: async () => {},
    dataUltimaAtualizacaoCatalogos: async () => null,
  };
  Object.defineProperty(window.navigator, 'onLine', { value: true, writable: true, configurable: true });

  const { carregarScriptDoProjeto } = require('./carregar_script');
  const caminhoJs = path.join(__dirname, '..', 'static', 'interface', 'js');
  ['regras_horario.js', 'validadores_arquivos.js', 'exportar_cliente.js', 'regras_campos.js', 'rad_form.js'].forEach(
    (arquivo) => carregarScriptDoProjeto(window, path.join(caminhoJs, arquivo))
  );

  await esperar(80);

  const ctx = { window, document, chamadas };

  ctx.digitar = function (id, valor) {
    const campo = document.getElementById(id);
    campo.value = valor;
    campo.dispatchEvent(new window.Event('input', { bubbles: true }));
    return campo;
  };
  ctx.sairDoCampo = function (id) {
    document.getElementById(id).dispatchEvent(new window.Event('blur'));
  };
  // O aviso e o <p class="campo__erro"> ligado ao campo por aria-describedby.
  ctx.aviso = function (id) {
    const campo = document.getElementById(id);
    const idAviso = campo.getAttribute('aria-describedby');
    return idAviso ? document.getElementById(idAviso) : null;
  };
  ctx.avisoVisivel = function (id) {
    const aviso = ctx.aviso(id);
    return !!aviso && !aviso.hidden && aviso.textContent.trim() !== '';
  };
  ctx.textoDoAviso = function (id) {
    const aviso = ctx.aviso(id);
    return aviso && !aviso.hidden ? aviso.textContent : '';
  };
  ctx.clicarSincronizar = async function () {
    document.getElementById('botao-sincronizar-drive').dispatchEvent(new window.Event('click', { bubbles: true }));
    await esperar(40);
  };
  ctx.chamouSincronizacao = () => chamadas.some((c) => c.url === '/rad/sincronizar/');
  return ctx;
}

async function principal() {
  // ======================================================================
  // 1) Regras puras (funcoes do modulo RegrasCampos)
  // ======================================================================
  const base = await montarPagina();
  const R = base.window.RegrasCampos;

  assert(R.LIMITE_DIGITOS_OS === 11, 'limite de digitos da OS no formulario e 11');
  assert(R.verificarOs('') === null, 'OS vazia: sem aviso (quem cobra e a regra de obrigatorio)');
  assert(R.verificarOs('71000006649') === null, 'OS de 11 digitos (71000006649) e valida');
  assert(R.verificarOs('99999999999') === null, 'OS de 11 noves e valida');
  assert(R.verificarOs('4321') === null, 'OS curta e valida');
  const os12 = R.verificarOs('100000000000');
  assert(os12 && os12.includes('no máximo 11 dígitos') && os12.includes('Você digitou 12'), 'OS de 12 digitos: explica a regra e mostra quantos digitou');
  assert(R.verificarOs('0') !== null && R.verificarOs('-5') !== null, 'OS zero ou negativa: aviso');
  assert(R.verificarOs('1.5') !== null, 'OS decimal: aviso');

  assert(R.verificarResponsavel('x'.repeat(50)) === null, 'Responsavel com 50 caracteres e valido');
  const resp51 = R.verificarResponsavel('x'.repeat(51));
  assert(resp51 && resp51.includes('no máximo 50 caracteres') && resp51.includes('Você digitou 51'), 'Responsavel com 51: explica a regra');

  const hojeFixo = new base.window.Date(2026, 8, 30); // 30/09/2026
  assert(R.verificarDataAtividade('', { hoje: hojeFixo }) === null, 'Data vazia: sem aviso');
  assert(R.verificarDataAtividade('30/09/2026', { hoje: hojeFixo }) === null, 'Data de hoje e valida');
  assert(R.verificarDataAtividade('15/03/2024', { hoje: hojeFixo }) === null, 'Data passada e valida');
  assert(R.verificarDataAtividade('01/10/2026', { hoje: hojeFixo }).includes('posterior a hoje'), 'Data de amanha: aviso de data futura');
  assert(R.verificarDataAtividade('31/02/2026', { hoje: hojeFixo }).includes('não existe'), '31/02 nao existe: aviso');
  assert(R.verificarDataAtividade('15/03/20', { hoje: hojeFixo, aoDigitar: true }) === null, 'Data incompleta ENQUANTO digita: sem aviso');
  assert(R.verificarDataAtividade('15/03/20', { hoje: hojeFixo, aoDigitar: false }).includes('completa'), 'Data incompleta ao sair do campo: aviso');

  // ======================================================================
  // 2) No formulario real: OS
  // ======================================================================
  const f1 = await montarPagina();
  f1.digitar('campo-numero-os', '100000000000');
  assert(f1.avisoVisivel('campo-numero-os'), 'OS com 12 digitos: aviso aparece abaixo do campo');
  assert(f1.textoDoAviso('campo-numero-os').includes('no máximo 11 dígitos'), 'o aviso diz qual e a regra (maximo 11 digitos)');
  assert(f1.document.getElementById('campo-numero-os').getAttribute('aria-invalid') === 'true', 'campo marcado como invalido (aria-invalid)');
  const aviso = f1.aviso('campo-numero-os');
  assert(aviso.previousElementSibling === f1.document.getElementById('campo-numero-os'), 'o aviso fica logo abaixo do proprio campo');

  f1.digitar('campo-numero-os', '71000006649');
  assert(!f1.avisoVisivel('campo-numero-os'), 'OS corrigida para 11 digitos: aviso some');
  assert(f1.document.getElementById('campo-numero-os').getAttribute('aria-invalid') === null, 'aria-invalid removido ao corrigir');

  // ======================================================================
  // 3) N° SA: letras apagadas COM explicacao
  // ======================================================================
  const f2 = await montarPagina();
  const sa = f2.digitar('campo-numero-sa', 'ab123');
  assert(sa.value === '123', 'N° SA: letras continuam sendo apagadas (valor 123)');
  assert(f2.avisoVisivel('campo-numero-sa') && f2.textoDoAviso('campo-numero-sa').includes('apenas números'), 'N° SA: o aviso explica que so aceita numeros');
  f2.digitar('campo-numero-sa', '12345');
  assert(!f2.avisoVisivel('campo-numero-sa'), 'N° SA: aviso some quando o texto volta a ser valido');

  // limite de caracteres (maxlength=10) com mensagem propria
  const campoSa = f2.document.getElementById('campo-numero-sa');
  campoSa.value = '1234567890';
  campoSa.dispatchEvent(new f2.window.InputEvent('beforeinput', { data: '1', inputType: 'insertText', bubbles: true, cancelable: true }));
  assert(f2.textoDoAviso('campo-numero-sa') === 'O N° SA aceita no máximo 10 dígitos.', 'N° SA: tentar digitar o 11o digito mostra a regra');

  // ======================================================================
  // 4) Responsavel Atividade (maximo 50)
  // ======================================================================
  const f3 = await montarPagina();
  f3.digitar('campo-responsavel-atividade', 'y'.repeat(50));
  assert(!f3.avisoVisivel('campo-responsavel-atividade'), 'Responsavel com 50 caracteres: sem aviso');
  f3.digitar('campo-responsavel-atividade', 'y'.repeat(51));
  assert(f3.avisoVisivel('campo-responsavel-atividade') && f3.textoDoAviso('campo-responsavel-atividade').includes('50 caracteres'), 'Responsavel com 51: aviso com a regra');

  // ======================================================================
  // 5) Data da Atividade
  // ======================================================================
  const f4 = await montarPagina();
  f4.digitar('campo-data-atividade', '31/02/2026');
  assert(f4.textoDoAviso('campo-data-atividade').includes('não existe'), 'Data da Atividade 31/02: aviso de data inexistente');
  const linhaData = f4.document.querySelector('.campo-data-atividade__linha');
  assert(f4.aviso('campo-data-atividade').previousElementSibling === linhaData, 'aviso da data fica DEPOIS da linha (campo + calendario), nao no meio dela');
  f4.digitar('campo-data-atividade', '01/01/2099');
  assert(f4.textoDoAviso('campo-data-atividade').includes('posterior a hoje'), 'Data da Atividade futura: aviso');
  f4.digitar('campo-data-atividade', '15/03/2024');
  assert(!f4.avisoVisivel('campo-data-atividade'), 'Data da Atividade valida: sem aviso');
  f4.digitar('campo-data-atividade', '15/03/20');
  assert(!f4.avisoVisivel('campo-data-atividade'), 'Data incompleta durante a digitacao: sem aviso');
  f4.sairDoCampo('campo-data-atividade');
  assert(f4.textoDoAviso('campo-data-atividade').includes('completa'), 'Data incompleta ao sair do campo: aviso');

  // ======================================================================
  // 6) Km/Poste e Terceiros: texto descartado COM explicacao
  // ======================================================================
  const f5 = await montarPagina();
  const km = f5.digitar('campo-km-poste-inicial', '12ab345');
  assert(km.value === '12/34 + 5', 'Km/Poste: mascara continua funcionando (12/34 + 5)');
  assert(f5.textoDoAviso('campo-km-poste-inicial').includes('apenas números'), 'Km/Poste: aviso explica que so aceita numeros');
  f5.digitar('campo-km-poste-inicial', '1234567');
  assert(!f5.avisoVisivel('campo-km-poste-inicial'), 'Km/Poste valido: sem aviso');
  const campoKm = f5.document.getElementById('campo-km-poste-inicial');
  campoKm.dispatchEvent(new f5.window.InputEvent('beforeinput', { data: '8', inputType: 'insertText', bubbles: true, cancelable: true }));
  assert(f5.textoDoAviso('campo-km-poste-inicial').includes('no máximo 7 números'), 'Km/Poste: digitar alem do limite mostra a regra (7 numeros)');

  const ter = f5.digitar('campo-terceiros-ajudantes', 'x9');
  assert(ter.value === '9' && f5.textoDoAviso('campo-terceiros-ajudantes').includes('apenas números'), 'Terceiros: letra apagada com explicacao');

  // ======================================================================
  // 7) Limite generico de caracteres (qualquer campo com maxlength)
  // ======================================================================
  const f6 = await montarPagina();
  const obs = f6.document.getElementById('campo-observacoes-gerais');
  obs.value = 'a'.repeat(3000);
  obs.dispatchEvent(new f6.window.InputEvent('beforeinput', { data: 'b', inputType: 'insertText', bubbles: true, cancelable: true }));
  assert(f6.textoDoAviso('campo-observacoes-gerais') === 'Limite de 3000 caracteres atingido.', 'Observacoes: passar do limite mostra "Limite de 3000 caracteres atingido."');
  obs.value = 'a'.repeat(10);
  obs.dispatchEvent(new f6.window.InputEvent('beforeinput', { data: 'b', inputType: 'insertText', bubbles: true, cancelable: true }));
  assert(f6.textoDoAviso('campo-observacoes-gerais') === 'Limite de 3000 caracteres atingido.', 'aviso anterior segue ate sumir sozinho (temporario)');

  // Teclado de celular (composicao de palavra): NAO pode gerar aviso falso
  const f6b = await montarPagina();
  const obs2 = f6b.document.getElementById('campo-observacoes-gerais');
  obs2.value = 'a'.repeat(2998) + 'bc'; // 3000 caracteres, palavra "bc" ainda em formacao
  obs2.dispatchEvent(new f6b.window.InputEvent('beforeinput', { data: 'bc', inputType: 'insertCompositionText', bubbles: true, cancelable: true }));
  assert(!f6b.avisoVisivel('campo-observacoes-gerais'), 'composicao de palavra (teclado de celular) nao gera aviso de limite falso');

  // ======================================================================
  // 8) Sincronizacao: bloqueada com campo fora da regra, liberada sem isso
  // ======================================================================
  const f7 = await montarPagina();
  f7.digitar('campo-numero-os', '100000000000');
  await f7.clicarSincronizar();
  assert(!f7.chamouSincronizacao(), 'OS com 12 digitos: o RAD NAO e enviado ao servidor');
  const lista = f7.document.getElementById('lista-erros-sincronizacao');
  assert(lista.textContent.includes('no máximo 11 dígitos'), 'a lista de erros mostra a regra violada');
  assert(f7.document.activeElement === f7.document.getElementById('campo-numero-os'), 'o foco vai para o campo com problema');

  f7.digitar('campo-numero-os', '71000006649');
  await f7.clicarSincronizar();
  assert(f7.chamouSincronizacao(), 'OS corrigida: a sincronizacao e enviada');

  // varios campos fora da regra: todos aparecem na lista
  const f8 = await montarPagina();
  f8.digitar('campo-numero-os', '100000000000');
  f8.digitar('campo-responsavel-atividade', 'z'.repeat(60));
  f8.digitar('campo-data-atividade', '01/01/2099');
  await f8.clicarSincronizar();
  const itens = f8.document.querySelectorAll('#lista-erros-sincronizacao li');
  assert(itens.length === 3 && !f8.chamouSincronizacao(), 'tres campos fora da regra: tres itens na lista e nada enviado');

  // campo ESCONDIDO (desabilitado em Configuracoes) nao conta
  const f9 = await montarPagina();
  f9.digitar('campo-numero-os', '100000000000');
  f9.document.querySelector('[data-config-campo="numero_os"]').style.display = 'none';
  await f9.clicarSincronizar();
  assert(f9.chamouSincronizacao(), 'campo escondido (desabilitado) fora da regra nao bloqueia a sincronizacao');

  // ======================================================================
  // 9) Robustez: resposta inesperada de /configuracoes/campos/ nao derruba o formulario
  // ======================================================================
  const f10 = await montarPagina({ respostaConfiguracoes: { ok: true, json: async () => ({}) } });
  f10.digitar('campo-numero-os', '100000000000');
  assert(f10.avisoVisivel('campo-numero-os'), 'resposta de configuracoes sem "campos": o formulario abre e os avisos funcionam');

  const f11 = await montarPagina({ respostaConfiguracoes: { ok: true, json: async () => { throw new Error('json invalido'); } } });
  f11.digitar('campo-numero-os', '100000000000');
  assert(f11.avisoVisivel('campo-numero-os'), 'resposta de configuracoes com JSON invalido: o formulario abre normalmente');

  console.log(falhas === 0 ? '\nTodos os testes passaram.' : `\n${falhas} teste(s) falharam.`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO no teste:', erro);
  process.exit(1);
});
