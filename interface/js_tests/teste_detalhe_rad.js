/*
 * Teste com DOM real (jsdom) da tela de detalhe do RAD: renderizacao
 * dos campos, exportacao (copiar mensagem) e fluxo de cancelamento
 * (RG-CAN-001 a 012).
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const caminhoHtml = process.argv[2];
if (!caminhoHtml) {
  console.error('Uso: node teste_detalhe_rad.js <caminho_para_html_renderizado>');
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
  const dom = new JSDOM(html, { url: 'http://localhost/consultar/R00001/', runScripts: 'dangerously' });
  const { window } = dom;
  const { document } = window;

  const chamadas = [];
  let textoRecortado = null;

  window.RadAuth = {
    exigirSessao: () => true,
    obterSessao: () => ({ login: 'admin.jsdom', perfis: ['administrador'] }),
    temPerfil: (...perfis) => perfis.includes('administrador'),
    requisicaoAutenticada: async (url, opcoes) => {
      chamadas.push({ url, opcoes });

      if (url.includes('/mensagem/')) {
        return { ok: true, json: async () => ({ mensagem: 'RAD - (Relatório de Atividade Diária)\n\nOS: 1234' }) };
      }
      if (url.includes('/cancelar/')) {
        const corpo = JSON.parse(opcoes.body);
        if (!corpo.justificativa) {
          return { ok: false, json: async () => ({ erro: 'A justificativa e obrigatoria.' }) };
        }
        return { ok: true, json: async () => ({ numero_rad: 'R00001', status: 'cancelado' }) };
      }
      // GET detalhe do RAD
      return {
        ok: true,
        status: 200,
        json: async () => ({
          numero_rad: 'R00001',
          numero_os: 1234,
          numero_sa: '5678',
          status: 'sincronizado',
          data_preenchimento: '2026-07-17',
          local_inicial: 'BFU',
          local_final: 'BFU',
          tipo_manutencao: 'Preventiva',
          responsavel_atividade: 'Carlos Souza',
          colaboradores: [{ nome: 'Fulano', tipo: 'colaborador', registro_empresa: '99999' }],
          anexos: [],
          amv: null,
          pode_cancelar: true,
          justificativa_cancelamento: null,
        }),
      };
    },
  };

  window.navigator.clipboard = {
    writeText: async (texto) => {
      textoRecortado = texto;
    },
  };

  document.dispatchEvent(new window.Event('DOMContentLoaded'));
  await new Promise((resolve) => setTimeout(resolve, 100));

  // ---- Renderizacao dos dados ----

  assert(
    document.getElementById('cartao-dados').style.display !== 'none',
    'cartao de dados aparece apos carregar o detalhe'
  );
  const textoCompleto = document.getElementById('lista-campos').textContent;
  assert(textoCompleto.includes('1234'), 'numero_os aparece nos dados renderizados');
  assert(textoCompleto.includes('Carlos Souza'), 'responsavel_atividade aparece nos dados renderizados');
  assert(
    document.getElementById('lista-colaboradores-detalhe').textContent.includes('Fulano'),
    'colaborador aparece na lista de colaboradores'
  );
  assert(
    document.getElementById('cartao-cancelar').style.display !== 'none',
    'bloco de cancelamento aparece quando pode_cancelar=true'
  );

  // ---- Copiar mensagem ----

  document.getElementById('botao-copiar-mensagem').dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 30));

  assert(textoRecortado !== null && textoRecortado.includes('OS: 1234'), 'mensagem copiada para a area de transferencia');
  assert(
    document.getElementById('aviso-exportar').textContent.includes('copiada'),
    'aviso de sucesso exibido apos copiar a mensagem'
  );

  // ---- Cancelamento: bloqueia sem justificativa ----

  document.getElementById('botao-abrir-cancelamento').dispatchEvent(new window.Event('click', { bubbles: true }));
  assert(document.getElementById('modal-cancelamento').style.display === 'flex', 'modal de cancelamento abre');

  document.getElementById('botao-confirmar-cancelamento').dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert(
    document.getElementById('aviso-modal-cancelamento').textContent.includes('Informe a justificativa'),
    'RG-CAN-005: bloqueia cancelamento sem justificativa'
  );
  assert(
    document.getElementById('modal-cancelamento').style.display === 'flex',
    'modal continua aberto quando falta justificativa (nao prossegue)'
  );

  // ---- Cancelamento: com justificativa, sucesso ----

  document.getElementById('campo-justificativa-cancelamento').value = 'SA duplicada por engano.';
  document.getElementById('botao-confirmar-cancelamento').dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 30));

  const chamadaCancelamento = chamadas.find((c) => c.url.includes('/cancelar/') && JSON.parse(c.opcoes.body).justificativa);
  assert(chamadaCancelamento !== undefined, 'POST de cancelamento enviado com justificativa preenchida');
  assert(chamadaCancelamento.opcoes.method === 'POST', 'metodo POST usado no cancelamento');
  // jsdom nao permite interceptar window.location.reload() de forma
  // simples (protege o objeto location); verificamos o sucesso pelo
  // efeito colateral que o codigo real garante ANTES de chamar reload:
  // o modal fechado (o "Not implemented: navigation" que aparece no
  // stderr depois disso e esperado -- e o jsdom recusando executar a
  // navegacao de verdade, nao um erro do nosso codigo).
  assert(
    document.getElementById('modal-cancelamento').style.display === 'none',
    'modal fecha apos cancelamento confirmado com sucesso (antes do reload da pagina)'
  );

  console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
  process.exit(falhas === 0 ? 0 : 1);
}

principal().catch((erro) => {
  console.error('ERRO INESPERADO:', erro);
  process.exit(1);
});
