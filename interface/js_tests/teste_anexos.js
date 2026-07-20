/*
 * Teste com DOM real (jsdom) do bloco Anexos.
 *
 * jsdom nao implementa createImageBitmap (decodificacao de imagem de
 * verdade exige um decoder nativo que o jsdom nao traz). Mockamos essa
 * API do navegador para simular "imagem valida" vs "imagem invalida"
 * de forma controlada -- o que testamos aqui e a nossa logica de
 * integracao (limites, add/remove, mensagens), nao o decoder de imagem
 * em si (esse e responsabilidade do proprio navegador). A validacao de
 * PDF (magic bytes via FileReader) roda de verdade, sem mock, porque
 * jsdom implementa FileReader/Blob/File nativamente.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_anexos.js <caminho_para_html_renderizado>');
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

  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'teste.jsdom', perfis: ['usuario'] }),
    temPerfil: () => false,
    requisicaoAutenticada: async () => ({ ok: true, json: async () => ({}) }),
  };
  window.RadDB = {
    obterCatalogo: async () => [],
    obterRascunho: async () => null,
    salvarRascunho: async () => {},
    dataUltimaAtualizacaoCatalogos: async () => null,
  };

  // Mock de createImageBitmap: arquivos cujo nome comece com "valida"
  // sao tratados como imagem decodificavel; qualquer outro nome falha
  // (simulando arquivo corrompido/invalido), igual ao comportamento
  // real do navegador para um arquivo que nao e uma imagem de verdade.
  window.createImageBitmap = function (arquivo) {
    if (arquivo.name.startsWith('valida')) {
      return Promise.resolve({ close: () => {} });
    }
    return Promise.reject(new Error('Nao decodificavel'));
  };
  window.URL.createObjectURL = function () {
    return 'blob:fake';
  };

  const { carregarScriptDoProjeto } = require('./carregar_script');
  const caminhoJs = path.join(__dirname, '..', 'static', 'interface', 'js');
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'regras_horario.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'validadores_arquivos.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'exportar_cliente.js'));
  carregarScriptDoProjeto(window, path.join(caminhoJs, 'rad_form.js'));

  await new Promise((resolve) => setTimeout(resolve, 50));

  function simularSelecaoArquivo(inputEl, arquivo) {
    Object.defineProperty(inputEl, 'files', { value: [arquivo], configurable: true });
    inputEl.dispatchEvent(new window.Event('change', { bubbles: true }));
  }

  const File = window.File;

  // ---- Fotos: Intervencao Verificada --------------------------------------

  const campoFotoIntervencao = document.getElementById('campo-foto-intervencao');

  const fotoValida1 = new File(['conteudo'], 'valida1.jpg', { type: 'image/jpeg' });
  simularSelecaoArquivo(campoFotoIntervencao, fotoValida1);
  await new Promise((resolve) => setTimeout(resolve, 20));

  const miniaturasIntervencao = document.getElementById('miniaturas-fotos-intervencao');
  assert(
    miniaturasIntervencao.children.length === 1,
    'primeira foto valida de Intervencao Verificada aparece na miniatura'
  );

  const fotoValida2 = new File(['conteudo'], 'valida2.jpg', { type: 'image/jpeg' });
  simularSelecaoArquivo(campoFotoIntervencao, fotoValida2);
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert(miniaturasIntervencao.children.length === 2, 'segunda foto valida tambem e adicionada');
  assert(
    campoFotoIntervencao.style.display === 'none',
    'ANX-003: input escondido ao atingir o limite de 2 fotos na categoria'
  );

  // ---- Foto invalida (corrompida) -----------------------------------------

  const campoFotoAcao = document.getElementById('campo-foto-acao');
  const fotoInvalida = new File(['nao-e-uma-imagem'], 'foto_corrompida.jpg', { type: 'image/jpeg' });
  simularSelecaoArquivo(campoFotoAcao, fotoInvalida);
  await new Promise((resolve) => setTimeout(resolve, 20));

  const miniaturasAcao = document.getElementById('miniaturas-fotos-acao');
  assert(miniaturasAcao.children.length === 0, 'foto invalida nao e adicionada');
  assert(
    document.getElementById('aviso-fotos-acao').textContent.includes('corrompido'),
    'mensagem de erro exibida para foto invalida'
  );

  // ---- Remover foto ---------------------------------------------------------

  const botaoRemoverPrimeiraFoto = miniaturasIntervencao.querySelector('button');
  botaoRemoverPrimeiraFoto.dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert(miniaturasIntervencao.children.length === 1, 'remover foto funciona');
  assert(
    campoFotoIntervencao.style.display !== 'none',
    'input reaparece depois de remover uma foto (deixou de estar no limite)'
  );

  // ---- PDF: valido (assinatura %PDF real) ------------------------------------

  const campoPdf = document.getElementById('campo-pdf');
  const pdfValido = new File(['%PDF-1.4 conteudo de pdf valido'], 'documento.pdf', {
    type: 'application/pdf',
  });
  simularSelecaoArquivo(campoPdf, pdfValido);
  await new Promise((resolve) => setTimeout(resolve, 20));

  const miniaturaPdf = document.getElementById('miniatura-pdf');
  assert(miniaturaPdf.children.length === 1, 'PDF valido (assinatura %PDF real, sem mock) e adicionado');
  assert(campoPdf.style.display === 'none', 'ANX-004: input de PDF escondido apos atingir o limite de 1');

  // ---- PDF invalido (sem assinatura %PDF) ------------------------------------

  // Remove o PDF adicionado para poder testar o caso invalido em seguida.
  miniaturaPdf.querySelector('button').dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 20));

  const pdfInvalido = new File(['isto-nao-e-um-pdf-de-verdade'], 'falso.pdf', {
    type: 'application/pdf',
  });
  simularSelecaoArquivo(campoPdf, pdfInvalido);
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert(
    document.getElementById('miniatura-pdf').children.length === 0,
    'PDF sem assinatura magica valida nao e adicionado (validacao real, sem mock)'
  );
  assert(
    document.getElementById('aviso-pdf').textContent.includes('não é um PDF válido'),
    'mensagem de erro exibida para PDF invalido'
  );

  console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO INESPERADO:', erro);
  process.exit(1);
});
