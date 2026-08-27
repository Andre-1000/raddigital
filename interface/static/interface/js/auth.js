/*
 * RadAuth — sessao do usuario (login sem senha, token de 7 dias).
 *
 * RG-AUTH-007/008: enquanto o token for valido, o acesso funciona
 * offline, sem bater no servidor. Por isso a validade e checada aqui,
 * localmente, comparando a data de expiracao salva no login com a hora
 * atual do dispositivo -- nunca fazendo uma requisicao so para
 * descobrir se o token ainda vale.
 *
 * 25/08/2026: essa checagem local (sessaoValida) so decide o que
 * aparece na TELA -- nao e o portao de seguranca de verdade. O portao
 * de verdade e o backend (usuarios/decorators.py::requer_token), que
 * confere o hash do token contra o banco em toda chamada real. Por
 * isso requisicaoAutenticada, abaixo, trata um 401 do servidor como
 * "sessao invalida", mesmo que sessaoValida() ainda achasse que
 * estava tudo certo.
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
   *
   * 25/08/2026: se o servidor responder 401 (token invalido/expirado
   * -- ver usuarios/decorators.py::requer_token), a sessao local esta
   * desatualizada mesmo que sessaoValida() ainda a considere valida
   * (checagem so local, ver comentario no topo do arquivo). Limpa a
   * sessao e manda pro login automaticamente, em vez de deixar a
   * pagina so mostrar "nao foi possivel..." sem dizer o motivo.
   */
  async function requisicaoAutenticada(url, opcoes = {}) {
    const sessao = obterSessao();
    const cabecalhos = Object.assign({}, opcoes.headers || {}, {
      Authorization: `Token ${sessao ? sessao.token : ''}`,
    });
    const resposta = await fetch(url, Object.assign({}, opcoes, { headers: cabecalhos }));
    if (resposta.status === 401) {
      limparSessao();
      window.location.href = '/entrar/';
    }
    return resposta;
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
