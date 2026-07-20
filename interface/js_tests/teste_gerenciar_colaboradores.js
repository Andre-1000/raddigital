/*
 * Teste com DOM real (jsdom) da tela Gerenciar Colaboradores.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_gerenciar_colaboradores.js <caminho_para_html_renderizado>');
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
  const dom = new JSDOM(html, { url: 'http://localhost/gerenciar-colaboradores/', runScripts: 'outside-only' });
  const { window } = dom;
  const { document } = window;

  const chamadas = [];
  // Estado simulado do "banco" -- comeca com um colaborador ativo.
  let colaboradores = [{ id: 1, registro_empresa: '11111', nome: 'Fulano', ativo: true }];
  let proximoId = 2;

  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'admin.jsdom', perfis: ['administrador'] }),
    temPerfil: (...perfis) => perfis.includes('administrador'),
    requisicaoAutenticada: async (url, opcoes) => {
      chamadas.push({ url, opcoes });
      const metodo = opcoes && opcoes.method ? opcoes.method : 'GET';

      if (url === '/colaboradores/administrar/') {
        return { ok: true, json: async () => ({ colaboradores }) };
      }
      if (url === '/colaboradores/' && metodo === 'POST') {
        const corpo = JSON.parse(opcoes.body);
        if (colaboradores.some((c) => c.registro_empresa === corpo.registro_empresa)) {
          return { ok: false, json: async () => ({ erros: [{ campo: 'registro_empresa', mensagem: 'Este registro ja esta cadastrado.' }] }) };
        }
        const novo = { id: proximoId++, registro_empresa: corpo.registro_empresa, nome: corpo.nome, ativo: true };
        colaboradores.push(novo);
        return { ok: true, json: async () => novo };
      }
      const matchEditar = url.match(/^\/colaboradores\/(\d+)\/editar\/$/);
      if (matchEditar && metodo === 'POST') {
        const id = Number(matchEditar[1]);
        const alvo = colaboradores.find((c) => c.id === id);
        const corpo = JSON.parse(opcoes.body);
        Object.assign(alvo, corpo);
        return { ok: true, json: async () => alvo };
      }
      const matchExcluir = url.match(/^\/colaboradores\/(\d+)\/excluir\/$/);
      if (matchExcluir && metodo === 'POST') {
        const id = Number(matchExcluir[1]);
        colaboradores = colaboradores.filter((c) => c.id !== id);
        return { ok: true, json: async () => ({ removido: true }) };
      }
      if (url === '/colaboradores/importar/' && metodo === 'POST') {
        const arquivo = opcoes.body.get('arquivo');
        const texto = await arquivo.text();
        const linhas = texto.split('\n').filter((l) => l.trim());
        let criados = 0;
        const erros = [];
        linhas.forEach((linha, indice) => {
          const [registro, nome] = linha.split(',').map((c) => (c || '').trim());
          if (!/^\d+$/.test(registro || '')) {
            erros.push({ linha: indice + 1, mensagem: 'Registro invalido.' });
            return;
          }
          colaboradores.push({ id: proximoId++, registro_empresa: registro, nome, ativo: true });
          criados++;
        });
        return { ok: true, json: async () => ({ criados, atualizados: 0, erros }) };
      }
      return { ok: false, json: async () => ({ erro: 'rota nao mockada: ' + url }) };
    },
  };

  const { carregarScriptDoProjeto } = require('./carregar_script');
  carregarScriptDoProjeto(
    window,
    path.join(__dirname, '..', 'static', 'interface', 'js', 'gerenciar_colaboradores.js')
  );
  await new Promise((resolve) => setTimeout(resolve, 80));

  // ---- Listagem inicial ----

  assert(
    document.getElementById('lista-colaboradores').textContent.includes('Fulano'),
    'colaborador existente aparece na listagem inicial'
  );

  // ---- Adicionar ----

  document.getElementById('campo-novo-registro').value = '22222';
  document.getElementById('campo-novo-nome').value = 'Novo Colaborador';
  document.getElementById('botao-adicionar').dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 50));

  assert(
    document.getElementById('lista-colaboradores').textContent.includes('Novo Colaborador'),
    'colaborador recem-adicionado aparece na lista apos recarregar'
  );
  assert(
    document.getElementById('aviso-criar').textContent.includes('adicionado'),
    'aviso de sucesso exibido ao adicionar'
  );

  // ---- Adicionar com registro duplicado -> erro ----

  document.getElementById('campo-novo-registro').value = '11111';
  document.getElementById('campo-novo-nome').value = 'Duplicado';
  document.getElementById('botao-adicionar').dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 50));

  assert(
    document.getElementById('aviso-criar').textContent.includes('já está cadastrado') ||
      document.getElementById('aviso-criar').textContent.includes('ja esta cadastrado'),
    'erro de registro duplicado exibido'
  );
  assert(
    !document.getElementById('lista-colaboradores').textContent.includes('Duplicado'),
    'colaborador duplicado nao foi adicionado'
  );

  // ---- Desativar ----

  const primeiroCartao = document.querySelector('#lista-colaboradores > div');
  const botaoDesativar = Array.from(primeiroCartao.querySelectorAll('button')).find((b) =>
    b.textContent.includes('Desativar')
  );
  assert(botaoDesativar !== undefined, 'botao Desativar encontrado para o colaborador ativo');
  botaoDesativar.dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 50));

  assert(colaboradores.find((c) => c.id === 1).ativo === false, 'colaborador foi desativado no backend simulado');
  assert(primeiroCartao.textContent.includes('Inativo'), 'selo "Inativo" aparece apos desativar');

  // ---- Editar ----

  const botaoEditar = Array.from(primeiroCartao.querySelectorAll('button')).find((b) =>
    b.textContent.includes('Editar')
  );
  botaoEditar.dispatchEvent(new window.Event('click', { bubbles: true }));

  const inputs = primeiroCartao.querySelectorAll('input');
  inputs[1].value = 'Fulano Editado';
  const botaoSalvar = Array.from(primeiroCartao.querySelectorAll('button')).find((b) =>
    b.textContent.includes('Salvar')
  );
  botaoSalvar.dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 50));

  assert(colaboradores.find((c) => c.id === 1).nome === 'Fulano Editado', 'nome editado gravado no backend simulado');
  assert(primeiroCartao.textContent.includes('Fulano Editado'), 'nome editado aparece na tela apos salvar');

  // ---- Excluir (com confirmacao) ----

  const botaoExcluir = Array.from(primeiroCartao.querySelectorAll('button')).find((b) =>
    b.textContent.includes('Excluir')
  );
  botaoExcluir.dispatchEvent(new window.Event('click', { bubbles: true }));

  assert(
    document.getElementById('modal-excluir-colaborador').style.display === 'flex',
    'modal de confirmacao de exclusao abre'
  );
  assert(
    document.getElementById('nome-colaborador-excluir').textContent === 'Fulano Editado',
    'modal menciona o nome certo do colaborador'
  );

  document.getElementById('botao-confirmar-exclusao-colaborador').dispatchEvent(
    new window.Event('click', { bubbles: true })
  );
  await new Promise((resolve) => setTimeout(resolve, 50));

  assert(
    !colaboradores.some((c) => c.id === 1),
    'colaborador removido do backend simulado apos confirmar'
  );
  assert(
    !document.getElementById('lista-colaboradores').textContent.includes('Fulano Editado'),
    'colaborador excluido desaparece da tela'
  );

  // ---- Importar CSV ----

  const File = window.File;
  const conteudoCsv = '55555,Importado Um\n66666,Importado Dois\nABC,Registro Invalido\n';
  const arquivoCsv = new File([conteudoCsv], 'lista.csv', { type: 'text/csv' });

  const campoArquivo = document.getElementById('campo-arquivo-importar');
  Object.defineProperty(campoArquivo, 'files', { value: [arquivoCsv], configurable: true });

  document.getElementById('botao-importar').dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 80));

  const listaTextoAposImportar = document.getElementById('lista-colaboradores').textContent;
  assert(listaTextoAposImportar.includes('Importado Um'), 'colaborador importado (linha 1) aparece na lista');
  assert(listaTextoAposImportar.includes('Importado Dois'), 'colaborador importado (linha 2) aparece na lista');

  const avisoImportar = document.getElementById('aviso-importar').textContent;
  assert(avisoImportar.includes('2'), 'resumo mostra a quantidade de criados');
  assert(
    avisoImportar.includes('1') && avisoImportar.toLowerCase().includes('não importada'),
    'resumo avisa sobre a linha com erro sem travar as outras'
  );

  console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO INESPERADO:', erro);
  process.exit(1);
});
