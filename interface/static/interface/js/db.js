/*
 * RadDB — armazenamento local (IndexedDB) do Sistema RAD.
 *
 * Duas responsabilidades, conforme PADROES_E_DIRETRIZES 5.2:
 * 1. Catalogos locais: espelho do que veio de GET /catalogos/todos/,
 *    atualizado na abertura da ferramenta quando ha conexao.
 * 2. Rascunho local: o RAD sendo preenchido, salvo a cada alteracao de
 *    campo, vinculado ao login do usuario (RG conforme EFD 3.8).
 *
 * Um unico banco IndexedDB ("sistema_rad"), com duas object stores:
 * "catalogos" (chave = nome do catalogo, ex: "linhas") e "rascunhos"
 * (chave = login do usuario -- um rascunho por usuario por vez, que e
 * o que a EFD descreve).
 */
const RadDB = (function () {
  const NOME_BANCO = 'sistema_rad';
  const VERSAO_BANCO = 1;
  const LOJA_CATALOGOS = 'catalogos';
  const LOJA_RASCUNHOS = 'rascunhos';

  let promessaConexao = null;

  function abrir() {
    if (promessaConexao) return promessaConexao;

    promessaConexao = new Promise((resolve, reject) => {
      const pedido = indexedDB.open(NOME_BANCO, VERSAO_BANCO);

      pedido.onupgradeneeded = function (evento) {
        const banco = evento.target.result;
        if (!banco.objectStoreNames.contains(LOJA_CATALOGOS)) {
          banco.createObjectStore(LOJA_CATALOGOS);
        }
        if (!banco.objectStoreNames.contains(LOJA_RASCUNHOS)) {
          banco.createObjectStore(LOJA_RASCUNHOS);
        }
      };

      pedido.onsuccess = function (evento) {
        resolve(evento.target.result);
      };

      pedido.onerror = function () {
        reject(pedido.error);
      };
    });

    return promessaConexao;
  }

  async function _set(nomeLoja, chave, valor) {
    const banco = await abrir();
    return new Promise((resolve, reject) => {
      const transacao = banco.transaction(nomeLoja, 'readwrite');
      transacao.objectStore(nomeLoja).put(valor, chave);
      transacao.oncomplete = () => resolve();
      transacao.onerror = () => reject(transacao.error);
    });
  }

  async function _get(nomeLoja, chave) {
    const banco = await abrir();
    return new Promise((resolve, reject) => {
      const transacao = banco.transaction(nomeLoja, 'readonly');
      const pedido = transacao.objectStore(nomeLoja).get(chave);
      pedido.onsuccess = () => resolve(pedido.result !== undefined ? pedido.result : null);
      pedido.onerror = () => reject(pedido.error);
    });
  }

  async function _delete(nomeLoja, chave) {
    const banco = await abrir();
    return new Promise((resolve, reject) => {
      const transacao = banco.transaction(nomeLoja, 'readwrite');
      transacao.objectStore(nomeLoja).delete(chave);
      transacao.oncomplete = () => resolve();
      transacao.onerror = () => reject(transacao.error);
    });
  }

  // ---- Catalogos ----------------------------------------------------

  /**
   * Busca GET /catalogos/todos/ e GET /colaboradores/todos/, gravando
   * cada catalogo (e o cadastro de colaboradores) em IndexedDB. So deve
   * ser chamada quando online (RG: catalogos atualizados na abertura da
   * ferramenta COM conexao). Lanca erro se offline ou se a requisicao
   * falhar -- quem chama decide se isso e critico ou nao (ex.: se ja
   * existe cache anterior, um erro aqui nao deveria travar a ferramenta).
   */
  async function atualizarCatalogos() {
    const [respostaCatalogos, respostaColaboradores] = await Promise.all([
      RadAuth.requisicaoAutenticada('/catalogos/todos/'),
      RadAuth.requisicaoAutenticada('/colaboradores/todos/'),
    ]);
    if (!respostaCatalogos.ok || !respostaColaboradores.ok) {
      throw new Error('Nao foi possivel atualizar os catalogos.');
    }
    const dados = await respostaCatalogos.json();
    const dadosColaboradores = await respostaColaboradores.json();

    const nomes = Object.keys(dados);
    for (const nome of nomes) {
      await _set(LOJA_CATALOGOS, nome, dados[nome]);
    }
    await _set(LOJA_CATALOGOS, 'colaboradores_cadastro', dadosColaboradores.colaboradores);
    await _set(LOJA_CATALOGOS, '_atualizado_em', new Date().toISOString());
    return dados;
  }

  /** Le um catalogo do cache local (ex.: RadDB.obterCatalogo('linhas')). */
  async function obterCatalogo(nome) {
    const valor = await _get(LOJA_CATALOGOS, nome);
    return valor || [];
  }

  async function dataUltimaAtualizacaoCatalogos() {
    return _get(LOJA_CATALOGOS, '_atualizado_em');
  }

  // ---- Rascunho local -------------------------------------------------

  /** Salva/atualiza o rascunho do RAD do usuario atual. */
  async function salvarRascunho(loginUsuario, rascunho) {
    rascunho.atualizado_em = new Date().toISOString();
    return _set(LOJA_RASCUNHOS, loginUsuario, rascunho);
  }

  async function obterRascunho(loginUsuario) {
    return _get(LOJA_RASCUNHOS, loginUsuario);
  }

  async function limparRascunho(loginUsuario) {
    return _delete(LOJA_RASCUNHOS, loginUsuario);
  }

  return {
    atualizarCatalogos,
    obterCatalogo,
    dataUltimaAtualizacaoCatalogos,
    salvarRascunho,
    obterRascunho,
    limparRascunho,
  };
})();
