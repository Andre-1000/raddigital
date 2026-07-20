/*
 * RadAuth — sessao do usuario (login sem senha, token de 7 dias).
 *
 * RG-AUTH-007/008: enquanto o token for valido, o acesso funciona
 * offline, sem bater no servidor. Por isso a validade e checada aqui,
 * localmente, comparando a data de expiracao salva no login com a hora
 * atual do dispositivo -- nunca fazendo uma requisicao so para
 * descobrir se o token ainda vale.
 */
const RadAuth = (function () {
  const CHAVE_SESSAO = 'rad_sessao';

  function salvarSessao(dados) {
    // dados: {login, token, validade, perfis}
    localStorage.setItem(CHAVE_SESSAO, JSON.stringify(dados));
  }

  function obterSessao() {
    const bruto = localStorage.getItem(CHAVE_SESSAO);
    if (!bruto) return null;
    try {
      return JSON.parse(bruto);
    } catch (erro) {
      return null;
    }
  }

  function limparSessao() {
    localStorage.removeItem(CHAVE_SESSAO);
  }

  function sessaoValida() {
    const sessao = obterSessao();
    if (!sessao || !sessao.token || !sessao.validade) return false;
    return new Date(sessao.validade).getTime() > Date.now();
  }

  function temPerfil(...perfis) {
    const sessao = obterSessao();
    if (!sessao || !sessao.perfis) return false;
    return perfis.some((p) => sessao.perfis.includes(p));
  }

  /**
   * Garante que a pagina atual exige sessao valida. Se nao houver,
   * redireciona para o login e interrompe a execucao do restante do
   * script da pagina (quem chamar deve parar apos receber false).
   */
  function exigirSessao() {
    if (!sessaoValida()) {
      limparSessao();
      window.location.href = '/entrar/';
      return false;
    }
    return true;
  }

  function sair() {
    limparSessao();
    window.location.href = '/entrar/';
  }

  /**
   * fetch() com o cabecalho Authorization ja preenchido. Uso identico
   * ao fetch nativo para o resto (body, method, etc.).
   */
  async function requisicaoAutenticada(url, opcoes = {}) {
    const sessao = obterSessao();
    const cabecalhos = Object.assign({}, opcoes.headers || {}, {
      Authorization: `Token ${sessao ? sessao.token : ''}`,
    });
    return fetch(url, Object.assign({}, opcoes, { headers: cabecalhos }));
  }

  return {
    salvarSessao,
    obterSessao,
    limparSessao,
    sessaoValida,
    temPerfil,
    exigirSessao,
    sair,
    requisicaoAutenticada,
  };
})();
