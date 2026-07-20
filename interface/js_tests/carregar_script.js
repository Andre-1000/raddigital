/*
 * Helper compartilhado pelos testes jsdom: carrega um arquivo JS do
 * projeto e executa no contexto da `window` de teste.
 *
 * Por que isso existe: os modulos do projeto usam
 * `const NomeDoModulo = (function () { ... })();` no escopo global de
 * cada <script>. Em um navegador de verdade, declaracoes const/let de
 * nivel superior de tags <script> diferentes convivem no mesmo escopo
 * lexico global e continuam visiveis para os scripts seguintes -- mas
 * o comportamento de window.eval() do jsdom para const de nivel
 * superior nem sempre expoe o nome como propriedade de window de
 * forma confiavel entre chamadas separadas. Isso so foi percebido
 * quando um teste realmente EXERCITOU o modulo em questao (testes
 * anteriores que nao acionavam o codigo que usa RegrasHorario
 * passaram "por acidente", mascarando o problema).
 *
 * Solucao: reescreve `const NomeDoModulo` para `window.NomeDoModulo`
 * antes de avaliar, garantindo que o modulo sempre fique acessivel
 * como propriedade real de window, independente do comportamento
 * especifico do jsdom.
 */
const fs = require('fs');

/*
 * Nota para quem for escrever um novo teste jsdom: NAO disparar
 * DOMContentLoaded manualmente com document.dispatchEvent(...) --
 * o jsdom ja dispara esse evento sozinho, de forma automatica e
 * assincrona, ao terminar de montar o documento. Um dispatch manual
 * ADICIONAL faz qualquer listener registrado nesse evento rodar DUAS
 * vezes (bug real encontrado durante o desenvolvimento: cada clique em
 * "Sincronizar" disparava duas chamadas de rede). Basta esperar um
 * pouco (setTimeout) apos carregar os scripts para o evento automatico
 * já ter disparado.
 */
function carregarScriptDoProjeto(window, caminhoAbsoluto) {
  let codigo = fs.readFileSync(caminhoAbsoluto, 'utf8');
  codigo = codigo.replace(/^const (\w+) = /m, 'window.$1 = ');
  window.eval(codigo);
}

module.exports = { carregarScriptDoProjeto };
