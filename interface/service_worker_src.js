/*
 * Service Worker do Sistema RAD.
 *
 * Responsabilidade: fazer o "app shell" (as paginas HTML + CSS/JS)
 * carregar mesmo sem conexao -- inclusive na primeira tentativa de
 * abrir a ferramenta depois que o navegador ja visitou o site uma vez
 * (RG-SYNC-001/010/011). Sem isso, o app so funcionava offline DEPOIS
 * de a pagina ja ter carregado uma vez naquela sessao -- recarregar a
 * pagina, ou abrir o navegador do zero, sem sinal, simplesmente nao
 * funcionava.
 *
 * Deliberadamente NAO intercepta nenhuma rota de API (/rad/,
 * /catalogos/, /colaboradores/, /consulta/, /configuracoes/,
 * /usuarios/, /admin/, /media/): essas ja tem sua propria estrategia de
 * offline via RadDB (IndexedDB) implementada em db.js e rad_form.js.
 * Deixar o Service Worker cachear essas respostas tambem criaria DUAS
 * fontes de verdade para os mesmos dados (o cache HTTP do SW e o
 * IndexedDB), que podem ficar dessincronizadas -- por exemplo, servir
 * uma resposta de catalogo desatualizada do cache do SW por baixo do
 * pano, escondendo do usuario que os catalogos no IndexedDB estao
 * desatualizados de verdade (o que RadDB.dataUltimaAtualizacaoCatalogos
 * informa corretamente na tela).
 *
 * Estrategia para o app shell: network-first com fallback para cache.
 * Sempre tenta buscar a versao mais nova quando ha conexao (e atualiza
 * o cache), e so usa o cache quando a rede falha. Isso evita servir uma
 * versao desatualizada da ferramenta para quem esta online.
 */

const NOME_CACHE = 'sistema-rad-v2';

const URLS_APP_SHELL = [
  '/',
  '/entrar/',
  '/inicio/',
  '/novo-rad/',
  '/consultar/',
  '/static/interface/css/estilo.css',
  '/static/interface/js/auth.js',
  '/static/interface/js/db.js',
  '/static/interface/js/regras_horario.js',
  '/static/interface/js/validadores_arquivos.js',
  '/static/interface/js/exportar_cliente.js',
  '/static/interface/js/rad_form.js',
  '/static/interface/js/vendor/jspdf.umd.min.js',
];

// Prefixos de rota que o Service Worker nunca deve interceptar --
// sempre vao direto para a rede, sem cache nenhum aqui.
const PREFIXOS_NUNCA_CACHEAR = [
  '/usuarios/',
  '/rad/',
  '/catalogos/',
  '/colaboradores/',
  '/consulta/',
  '/configuracoes/',
  '/admin/',
  '/media/',
  '/sw.js',
];

self.addEventListener('install', function (evento) {
  evento.waitUntil(
    caches
      .open(NOME_CACHE)
      .then(function (cache) {
        return cache.addAll(URLS_APP_SHELL);
      })
      .then(function () {
        // Ativa este SW imediatamente, sem esperar todas as abas
        // antigas fecharem -- a versao nova do app shell deve valer
        // assim que possivel.
        return self.skipWaiting();
      })
  );
});

self.addEventListener('activate', function (evento) {
  evento.waitUntil(
    caches
      .keys()
      .then(function (nomesExistentes) {
        return Promise.all(
          nomesExistentes
            .filter(function (nome) {
              return nome !== NOME_CACHE;
            })
            .map(function (nome) {
              return caches.delete(nome);
            })
        );
      })
      .then(function () {
        return self.clients.claim();
      })
  );
});

function ehRotaDeApi(url) {
  return PREFIXOS_NUNCA_CACHEAR.some(function (prefixo) {
    return url.pathname.startsWith(prefixo);
  });
}

self.addEventListener('fetch', function (evento) {
  const url = new URL(evento.request.url);

  // So GET e cacheavel (POST/PUT/DELETE nunca devem ser interceptados);
  // e nunca mexer em rotas de API -- ver comentario no topo do arquivo.
  if (evento.request.method !== 'GET' || ehRotaDeApi(url)) {
    return;
  }

  evento.respondWith(
    fetch(evento.request)
      .then(function (respostaDeRede) {
        const copiaParaCache = respostaDeRede.clone();
        caches.open(NOME_CACHE).then(function (cache) {
          cache.put(evento.request, copiaParaCache);
        });
        return respostaDeRede;
      })
      .catch(function () {
        return caches.match(evento.request);
      })
  );
});
