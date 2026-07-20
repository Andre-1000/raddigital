# Sistema RAD — Ambiente de Desenvolvimento Local

Relatório de Atividade Diária — CPTM. Django + PostgreSQL.

## 1. Pré-requisitos
- Python 3.12+
- PostgreSQL 14+ instalado e rodando localmente
- Node.js 18+ (só para rodar os testes de JS do frontend — `interface/tests.py` invoca `node` para testar `regras_horario.js` e o bloco AMV com DOM real via jsdom)
- Playwright com Chromium (só para o teste do Service Worker — `pip install playwright && playwright install chromium`), único jeito de testar offline de verdade num navegador real

## 2. Instalar o PostgreSQL

### Windows
1. Baixe o instalador em https://www.postgresql.org/download/windows/
2. Durante a instalação, defina uma senha para o usuário `postgres` (anote-a).
3. Mantenha a porta padrão `5432`.
4. Ao final, abra o **SQL Shell (psql)** pelo menu iniciar e rode:
   ```sql
   CREATE USER rad_dev WITH PASSWORD 'sua_senha_aqui' CREATEDB;
   CREATE DATABASE sistema_rad OWNER rad_dev;
   ```

### macOS
```bash
brew install postgresql@16
brew services start postgresql@16
createuser -s rad_dev
psql -U rad_dev -d postgres -c "ALTER USER rad_dev WITH PASSWORD 'sua_senha_aqui';"
psql -U rad_dev -d postgres -c "CREATE DATABASE sistema_rad OWNER rad_dev;"
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER rad_dev WITH PASSWORD 'sua_senha_aqui' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE sistema_rad OWNER rad_dev;"
```

## 3. Configurar o projeto
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edite o .env e coloque a senha que você definiu para rad_dev

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse http://localhost:8000/admin/ para o painel administrativo.

## 4. Rodar os testes
```bash
# Uma vez, para instalar as dependências dos testes JS (jsdom)
cd interface/js_tests && npm install && cd ../..

# Uma vez, para instalar o Chromium usado no teste do Service Worker
playwright install chromium

pytest -v --cov=. --cov-report=term-missing
```

## 5. Rodar os seeds de catálogo
Depois de migrar, popule os catálogos com os arquivos em `seeds_sql/`:
```bash
psql -U rad_dev -d sistema_rad -f seeds_sql/seed_cat_linhas.sql
# ... demais arquivos (os catálogos ainda não têm modelos Django — ver pendências)
```

## 6. Testar o login (endpoint pronto)
```bash
# Criar um usuário de teste no shell do Django
python manage.py shell -c "from usuarios.models import Usuario, UsuarioPerfil; u = Usuario.objects.create(login='teste.dev'); UsuarioPerfil.objects.create(usuario=u, perfil='administrador')"

# Fazer login
curl -X POST http://localhost:8000/usuarios/login/ \
  -H "Content-Type: application/json" \
  -d '{"login": "teste.dev"}'
```

## 7. Testar a sincronização de um RAD (endpoint pronto)
Depois de carregar os catálogos (passo 5) e obter um token (passo 6):
```bash
curl -X POST http://localhost:8000/rad/sincronizar/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token SEU_TOKEN_AQUI" \
  -d '{
    "numero_os": 1234,
    "numero_sa": "5678",
    "data_preenchimento": "2026-06-15",
    "id_local_inicial": "BFU",
    "id_local_final": "LUZ",
    "linhas": ["11"],
    "vias": [1],
    "id_tipo_manutencao": 2,
    "hora_prog_inicio": "08:00",
    "hora_prog_termino": "12:00",
    "hora_real_inicio": "08:00",
    "hora_real_termino": "12:00",
    "servicos": [1],
    "colaboradores": [{"registro_empresa": null, "nome": "Fulano", "tipo": "participante"}],
    "sync_id_tentativa": "teste-manual-0001"
  }'
```
Nota: para enviar um colaborador com `"tipo": "colaborador"` (em vez de `"participante"`), o `registro_empresa` precisa existir antes no cadastro oficial (`POST /colaboradores/`, exclusivo do Administrador) — caso contrário a sincronização é bloqueada (VLD-027).

Se algum campo estiver ausente ou inválido, a resposta vem com status 422 e a lista completa de erros (código VLD, campo, mensagem).

Com anexos (multipart, campo `dados` leva o mesmo JSON acima como string):
```bash
curl -X POST http://localhost:8000/rad/sincronizar/ \
  -H "Authorization: Token SEU_TOKEN_AQUI" \
  -F 'dados={"numero_os":1234, "numero_sa":"5678", ... "sync_id_tentativa":"teste-anexo-0001"}' \
  -F "fotos_intervencao_verificada=@/caminho/foto1.jpg" \
  -F "fotos_acao_realizada=@/caminho/foto2.jpg" \
  -F "pdf=@/caminho/documento.pdf"
```

## 8. Exportar um RAD já sincronizado (mensagem e PDF)
```bash
# Mensagem "Copiar msg"
curl http://localhost:8000/consulta/rads/R00001/mensagem/ \
  -H "Authorization: Token SEU_TOKEN_AQUI"

# PDF (baixa o arquivo)
curl http://localhost:8000/consulta/rads/R00001/pdf/ \
  -H "Authorization: Token SEU_TOKEN_AQUI" \
  -o R00001.pdf

# Word (baixa o arquivo)
curl http://localhost:8000/consulta/rads/R00001/docx/ \
  -H "Authorization: Token SEU_TOKEN_AQUI" \
  -o R00001.docx
```
Acesso: Supervisor, Administrador, ou o próprio técnico que criou o RAD.


## Status atual do desenvolvimento
- [x] Projeto Django criado com apps: usuarios, rad, catalogos, consulta, colaboradores
- [x] App `usuarios`: modelos (Usuario, UsuarioPerfil, Token), login sem senha, validação de token, decorators de permissão
- [x] App `catalogos`: 9 modelos + comando `carregar_catalogos` (seeds validados: 3+70+4+5+13+4+238+17+7 registros)
- [x] App `rad`: modelo de dados completo (rad + 8 tabelas relacionadas)
- [x] Regra crítica RG-IDENT-008/009: geração atômica do Número de Execução (lock consultivo do Postgres) e do Número do RAD (sequence dedicada) — testado com concorrência real (8 threads simultâneas, sem colisão)
- [x] Idempotência de sincronização (sync_id_tentativa)
- [x] Regra RG-HOR-001 a 027: virada de meia-noite, cálculo de duração e atraso (com tolerância) — inclui o exemplo oficial da EFD (22:00→02:00 = 4h00)
- [x] Validações RG-VLD-001 a 003 / VLD-001 a VLD-022 (todas exceto VLD-023/024, que dependem do upload de anexos)
- [x] Endpoint `POST /rad/sincronizar/` — orquestra token → validação → horários → gravação atômica → tabelas relacionadas (linhas, vias, serviços, colaboradores, bloco AMV)
- [x] Endpoint `POST /rad/<numero_rad>/cancelar/` — RG-CAN-001 a 012 (exclusivo Administrador, justificativa obrigatória, irreversível)
- [x] App `consulta`: `GET /consulta/rads/` (14 filtros combináveis, paginação de 15, total exibido) e `GET /consulta/rads/<numero_rad>/` (detalhe completo, botão cancelar visível só para Administrador) — PRM-028 a PRM-038
- [x] Anexos (fotos e PDF): upload via `multipart/form-data` no próprio `/rad/sincronizar/`, validação real de conteúdo (não só extensão) com Pillow/pypdf — VLD-023/024 —, limites de quantidade e tamanho (RG-ANX-003/004/005), remoção exclusiva do Administrador (RG-ANX-011). **Fotos divididas em dois grupos com tema próprio, até 2 cada (4 no total)**: "Intervenção verificada" (`fotos_intervencao_verificada`) e "Ação realizada" (`fotos_acao_realizada`) — nunca misturadas sem identificação, com constraint no próprio banco garantindo que toda foto tenha categoria e todo PDF não tenha
- [x] App `colaboradores`: cadastro oficial de funcionários (CRUD exclusivo do Administrador — RG-RESP-012), busca por registro/nome para qualquer usuário logado (RG-RESP-003/008), e correção de integridade: o nome do colaborador gravado no RAD vem do cadastro oficial, não do que o cliente enviou (RG-RESP-004/005/010) — participantes externos preservam o nome como enviado (RG-RESP-013/014)
- [x] **Mudança de negócio (16/07/2026)**: campo "SA" renomeado para "OS" (`numero_os`) — mesmas validações e regras (VLD-001, RG-IDENT-004 a 012); novo campo independente **"N° SA"** (`numero_sa`) adicionado — numérico, até 10 caracteres, obrigatório (nova regra VLD-028); catálogo de vias já continha Via 3 e Via 4 (nada a fazer)
- [x] **Mudança de negócio (17/07/2026)**:
  - Campo **"Responsável Atividade"** — texto, até 50 caracteres, obrigatório (VLD-029)
  - Campo **"Operador CCM"** — texto, até 25 caracteres, opcional (VLD-030)
  - Campo **"Descrição Técnica da Atividade"** — sem limite de caracteres, aceita qualquer conteúdo (testado com acentos, símbolos e texto longo)
  - Campo **"Equipes Envolvidas"** — multi-seleção (RA, VP, CIVIL, RESTAB, SINAL, MRO), novo catálogo `cat_equipes`; **VP é sempre incluída automaticamente**, mesmo que o cliente não a envie (testado: nunca duplica se o cliente também enviar VP explicitamente)
  - **App `configuracoes` (novo)**: qualquer campo do formulário pode ser desabilitado pelo Administrador (`POST /configuracoes/campos/<chave>/desabilitar/`) — quando desabilitado, o campo deixa de ser exigido na sincronização *e* desaparece das respostas de consulta (listagem e detalhe) para **todos os perfis, inclusive Administrador**, até ser reabilitado. 31 campos do formulário já pré-cadastrados via migration de dados. Filtro genérico (não precisa tocar em cada validação/view individualmente)
- [x] **Exportação (17/07/2026)**: mensagem "Copiar msg", PDF **e Word** (`GET /consulta/rads/<numero_rad>/mensagem/`, `/pdf/` e `/docx/`), seguindo a estrutura original da EFD 3.13 com todos os campos das mudanças de negócio recentes incluídos — RG-EXP-003 (dois formatos) atendido. Acesso: Supervisor, Administrador, ou o próprio criador do RAD. Fonte única de campos compartilhada entre os três formatos (`rad/exportacao.py::_campos_do_relatorio`), testado que PDF e Word nunca divergem
- [x] 289 testes automatizados — todos passando, 96% de cobertura
- [x] **Revisão final (18/07/2026)**: nenhum segredo hardcoded fora do `.env`, `.gitignore` reforçado, suíte inteira rodando a partir de uma cópia extraída do zip do zero (sem dependência oculta do ambiente de desenvolvimento), checklist de produção adicionado. Investiguei as lacunas de cobertura (estava em 96%, não 100%) e encontrei 11 caminhos de erro genuinamente nunca testados — a maioria JSON malformado e limites numéricos não exercitados (mesmo padrão que revelou o bug do colaborador duplicado antes): OS com mais de 7 dígitos, data de preenchimento ausente, PDF acima de 10MB, PDF com estrutura válida mas zero páginas, corpo de requisição inválido em três endpoints diferentes, `sync_id_tentativa` ausente, cancelar RAD inexistente, e um cenário de segurança real — usuário desativado *depois* de já ter um token válido em uso continua sendo recusado corretamente. `rad/views.py`, `usuarios/views.py` e `rad/validadores_arquivos.py` foram para 100%; o que resta são métodos triviais (`__str__`) e proteções contra mau uso de decorator, não caminhos de negócio
- [x] `comum/datas.py`: ponto único de parsing de data/hora (elimina a duplicação que causou o bug de datetime "naive" reaparecer duas vezes) + `pytest.ini` transforma esse warning específico do Django em erro de teste, permanentemente
- [x] **Frontend — início (17/07/2026)**: app `interface`, telas servidas como HTML pelo próprio Django (padrão do projeto: sem separação frontend/backend). Paleta própria do cliente (`#242472` marca/texto, `#11aa60` ação principal, `#fa5e13` atenção, `#fffcff` superfícies, `#b8300f` perigo — derivada do laranja), mobile-first, fontes de sistema (funciona offline, sem depender de webfonts externas)
  - `RadAuth` (`interface/static/interface/js/auth.js`): sessão em `localStorage`, validação de token **local** (RG-AUTH-007/008 — nunca bate no servidor só para checar validade), helper de fetch autenticado
  - `RadDB` (`interface/static/interface/js/db.js`): wrapper de IndexedDB — catálogos locais + rascunho do RAD por usuário, conforme PADROES_E_DIRETRIZES 5.2
  - Endpoint `GET /catalogos/todos/`: os 9 catálogos numa única resposta, pensado para popular o IndexedDB de uma vez em vez de 9 requisições separadas
  - Catálogos são atualizados automaticamente logo após o login (sabemos que há conexão nesse momento) e podem ser atualizados manualmente na tela inicial, com indicação de quando foi a última atualização
  - Tela de login (`/entrar/`) — só o campo de login, sem senha (RG-AUTH-001), grava sessão e redireciona
  - Tela inicial (`/inicio/`) e consulta básica (`/consultar/`) — protegidas no cliente via `RadAuth.exigirSessao()`
  - Testado de ponta a ponta: login → token → chamada autenticada em `/consulta/rads/` e `/catalogos/todos/` funcionando
  - 24 testes automatizados de contrato (campos que o JS espera batem com a API real) e de carregamento das telas
- [x] Formulário de preenchimento do RAD — completo em 7 blocos, rascunho local em IndexedDB, todos os campos/validações espelhando o backend
- [x] **Teste manual de ponta a ponta contra o servidor rodando de verdade (17/07/2026)**: login → catálogos → colaboradores → sincronização completa com anexo real → consulta (listagem e detalhe) → exportação (mensagem/PDF/DOCX) → cancelamento e irreversibilidade → todas as páginas e assets do frontend. Tudo funcionando.
  - [x] **Bug real encontrado e corrigido**: enviar o mesmo colaborador duas vezes no mesmo RAD derrubava o servidor com **HTTP 500** (`IntegrityError` não tratado vindo direto da constraint do banco) em vez de um erro de validação limpo. RG-RESP-009 só estava garantida no banco, não na camada de validação. Corrigido com nova regra **VLD-031** em `rad/validadores.py`, com teste de regressão confirmando 422 (não 500) tanto isoladamente quanto via HTTP real. Confirmei que `@transaction.atomic` já protegia o banco de dados parciais mesmo durante o crash — nenhuma limpeza manual foi necessária
  - [x] **Bloco 1/7 — Identificação + Localização (17/07/2026)**: `/novo-rad/`, `interface/static/interface/js/rad_form.js`. OS, N° SA, Data, Local Inicial/Final (busca por código ou nome), Linha/Via/Equipes (chips, VP sempre fixa e não pode ser desmarcada), Km/Poste (máscara automática XX/XX - XX/XX, RG-LOC-007), Tipo de Manutenção com botão de ajuda (EFD-010-A) e N° Falha condicional que limpa automaticamente ao trocar o tipo (RG-COP-009). Autosave a cada alteração de campo, no IndexedDB, sobrevive a fechar/reabrir o navegador
  - [x] **Bloco 2/7 — Horários (17/07/2026)**: `interface/static/interface/js/regras_horario.js`, espelho client-side de `rad/regras_horario.py` (mesmos nomes de função, mesma lógica) — virada de meia-noite, duração programada/real, atraso com tolerância de 10min no início e sem tolerância no término, tudo calculado offline. **Testado com Node.js de verdade** (não só sintaxe): 10 casos incluindo o exemplo oficial da EFD (22:00→02:00 = 4h00) e as bordas exatas de tolerância — roda como parte da suíte pytest (`TestLogicaJsDeHorarios`). Atraso é exibido como **calculado automaticamente**, não como botão editável: o backend sempre recalcula a partir dos horários e ignora qualquer valor enviado pelo cliente para esse campo, então uma UI "editável" seria enganosa — decisão documentada, backend pode ganhar suporte a override manual depois se for necessário
  - [x] Endpoint novo `GET /catalogos/todos/` usado para popular os selects/chips a partir do cache local
  - [x] Teste de contrato: as chaves do rascunho no JS batem literalmente com o payload que o backend espera — qualquer renomeação futura de um lado sem o outro quebra o teste
  - [x] **Bloco 3/7 — Serviços + Bloco AMV (17/07/2026)**: checkboxes de serviços com ajuda expansível por item (texto do catálogo), "Outros" abre descrição obrigatória (RG-EXE-004/005), "Manutenção em AMV" abre o bloco inteiro (busca de MCH, preenchimento automático de Modelo/Via/UR/Local/Linha, Tipo de Defeito e Ações). **Bug real pego durante o desenvolvimento**: os checkboxes de Tipo de Defeito/Ações perdiam a ligação com o rascunho ao esconder/mostrar o bloco AMV (closure presa a um array antigo) — corrigido e travado com um teste de **DOM real via jsdom** que simula cliques de verdade no HTML renderizado pelo Django (não é só checagem de sintaxe). Provei que o teste falha de verdade reintroduzindo o bug de propósito antes de restaurar a versão correta
  - [x] **Decisão documentada**: Modelo/Via/Local da MCH aparecem como somente-leitura no formulário, não editáveis como a EFD sugere — porque o backend (`rad/regras_negocio.py`) sempre grava os valores do catálogo, ignorando qualquer edição enviada pelo cliente. Uma UI editável seria enganosa; se quiser esse comportamento de verdade, o backend precisa ganhar suporte a isso primeiro
  - [x] **Bloco 4/7 — Colaboradores e Participantes (17/07/2026)**: busca **offline** (não bate no servidor a cada tecla — filtra o cadastro cacheado no IndexedDB), nome sempre vindo do cadastro oficial e nunca editável (RG-RESP-004/005), impede adicionar o mesmo registro duas vezes (RG-RESP-009), mensagem exata "Colaborador não localizado." (RG-RESP-008), participantes externos sem registro (RG-RESP-013/014), remoção livre antes de sincronizar (RG-RESP-007). Endpoint novo `GET /colaboradores/todos/` + `RadDB` agora cacheia o cadastro de colaboradores junto com os catálogos
  - [x] Teste de DOM real (jsdom) simulando busca, duplicidade, não-localizado e remoção — mesma técnica do Bloco 3, passou de primeira
  - [x] **Bloco 5/7 — Anexos (17/07/2026)**: fotos categorizadas (2 Intervenção Verificada + 2 Ação Realizada) e 1 PDF, captura direta da câmera no celular (`capture="environment"`). Validação de conteúdo de verdade no navegador — `validadores_arquivos.js`, espelho de `rad/validadores_arquivos.py`: fotos decodificadas de verdade com `createImageBitmap()` (equivalente ao `Pillow.verify()` do backend), PDF checado pela assinatura mágica `%PDF` real via `FileReader` (sem mock no teste). Limite por categoria esconde o campo de upload ao ser atingido, remoção reabilita
  - [x] **Bug de infraestrutura de teste pego e corrigido**: o `window.eval()` do jsdom não expõe de forma confiável `const NomeDoModulo = ...` como propriedade de `window` entre chamadas separadas — os testes dos Blocos 3 e 4 "passavam por acidente" porque nunca chegavam a exercitar `RegrasHorario` (só usado quando os horários são preenchidos). Só apareceu quando o teste de Anexos referenciou `ValidadoresArquivos` de forma incondicional. Corrigido com um helper compartilhado (`carregar_script.js`) que garante a exposição correta, e retroaplicado aos testes anteriores
  - [x] **Bloco 6/7 — Campos finais (17/07/2026)**: Responsável Atividade, Operador CCM, Descrição Técnica da Atividade, Materiais Utilizados, Observações Gerais — todos texto livre, sem lógica condicional. **Observações Gerais posicionada abaixo do bloco de Anexos**, conforme decisão registrada em `docs/NOTAS_LAYOUT_FRONTEND.md` — teste com checagem posicional trava essa exigência (compara a posição das duas seções no HTML renderizado, não só se os campos existem)
  - [x] **Bloco 7/7 — Sincronizar (17/07/2026) — FORMULÁRIO COMPLETO**: monta o payload inteiro a partir de todos os blocos anteriores, envia como `multipart/form-data` para `/rad/sincronizar/` de verdade. Botão sempre visível mas desabilitado sem conexão ("Sem conexão", RG-SYNC-006/026) ou durante o envio. Em caso de sucesso, limpa o rascunho local e redireciona (RG-SYNC-008/021); em caso de erro de validação (422), mostra **todos** os erros retornados pelo servidor sem apagar nada (RG-SYNC-012/017); em caso de falha de rede, mesma coisa. Botão "Apagar rascunho" com confirmação explícita (RG-SYNC-019/020/022)
  - [x] **Bug de backend pego neste bloco**: `data_hp_inicio`/`data_hr_inicio` (editáveis desde o Bloco 2) eram **silenciosamente ignorados** na sincronização — o backend sempre usava `data_preenchimento`, nunca lia o valor enviado pelo cliente. Corrigido em `rad/views.py::_normalizar_payload` e `rad/regras_negocio.py::_preparar_horarios`, com teste de regressão
  - [x] **Bug de infraestrutura de teste pego neste bloco**: o jsdom dispara `DOMContentLoaded` automaticamente — o disparo manual que eu vinha fazendo em todos os testes anteriores causava **cada listener rodar duas vezes** (cada clique de sincronizar chamava a API duas vezes). Corrigido em todos os 5 testes jsdom existentes, com nota permanente no helper compartilhado para não reintroduzir
  - **Formulário de preenchimento do RAD está funcionalmente completo** — os 7 blocos cobrem 100% dos campos e regras do backend já construído
- [x] **Service Worker (17/07/2026)**: `/sw.js` (servido na raiz do domínio — precisa cobrir todas as páginas, não só `/static/`). Cacheia o app shell inteiro (páginas HTML + CSS/JS), estratégia network-first com fallback para cache — sempre busca a versão mais nova quando online, só usa cache quando a rede falha. **Nunca intercepta rotas de API** (`/rad/`, `/catalogos/`, `/colaboradores/`, `/consulta/`, `/configuracoes/`, `/usuarios/`, `/admin/`, `/media/`) — essas continuam exclusivamente sob o `RadDB`/IndexedDB, para não ter duas fontes de verdade conflitantes para os mesmos dados
  - **Testado com navegador real (Playwright + Chromium, não jsdom)**: subi um servidor Django de verdade, abri num Chromium de verdade, deixei o Service Worker instalar, **desliguei a rede de verdade** (`context.set_offline`) e confirmei que a página `/novo-rad/` carrega mesmo assim — a prova real de que o app funciona offline desde a primeira abertura, não só depois que a página já carregou uma vez. Também confirmei que o redirecionamento de sessão expirada (`/novo-rad/` → `/entrar/`) continua funcionando offline, porque as duas páginas estão cacheadas
  - jsdom não implementa Cache API nem os eventos `install`/`activate`/`fetch` de um Service Worker — por isso este é o único teste do projeto que depende de um navegador real (Playwright), documentado como pré-requisito adicional
- [x] **Exportação client-side/offline (18/07/2026)** — RG-EXP-001 a 010. Botão "Exportar" ao lado do "Sincronizar" (RG-EXP-004), habilitado só quando os campos obrigatórios estão preenchidos (RG-EXP-005). Três opções, **nenhuma faz chamada de rede**: copiar mensagem, baixar PDF, baixar Word — geradas 100% no dispositivo, a partir do rascunho local + catálogos já cacheados no IndexedDB
  - `exportar_cliente.js` espelha exatamente a mesma lista/ordem de campos de `rad/exportacao.py::_campos_do_relatorio` (fonte única testada e comparada campo a campo com o backend), resolvendo IDs (linha, via, equipe, serviço, tipo de manutenção, motivo de atraso) para nomes usando os catálogos locais, sem bater no servidor
  - PDF via **jsPDF hospedado localmente** (`vendor/jspdf.umd.min.js`, não via CDN — mantém a filosofia de zero dependência de terceiros em runtime, essencial para funcionar offline desde o primeiro carregamento) — adicionado à lista de cache do Service Worker
  - Word via HTML servido com extensão `.doc` (o Word abre nativamente) — zero dependência de biblioteca, mais simples e confiável do que gerar um `.docx` binário no navegador sem bundler
  - **Testado com navegador real (Playwright), rede desligada de verdade**: injetei um rascunho no IndexedDB, desliguei a rede via `context.set_offline(True)`, cliquei em "Baixar PDF", e **extraí o texto do PDF baixado** confirmando que os dados do rascunho (OS, responsável) estão lá — prova real de RG-EXP-002, não dedução por leitura de código
  - 18 cenários com DOM real (jsdom) para a lógica pura: resolução de códigos para nomes, formato da mensagem, regra de habilitação do botão (RG-EXP-005), geração do Word
- [x] **Regra "um RAD por vez" (17/07/2026)** — RG-SYNC-018/019/020. Ao entrar em `/novo-rad/` com um rascunho já existente **e com conteúdo relevante** (OS, SA ou serviços preenchidos — um rascunho recém-criado e vazio não conta), a tela pergunta antes de mostrar qualquer coisa: "Continuar este RAD" ou "Apagar e começar um novo" (reaproveita o mesmo modal de confirmação de irreversibilidade já existente). Cancelar a exclusão volta para a pergunta original, em vez de deixar a tela travada sem nenhum modal
  - 12 cenários com DOM real (jsdom): sem rascunho não pergunta, rascunho vazio não pergunta, rascunho com conteúdo pergunta e mostra a OS certa, "Continuar" popula o formulário, "Apagar" → "Cancelar" volta ao conflito, "Apagar" → "Confirmar" limpa de verdade
  - **Testado com navegador real (Playwright)**: injetei um rascunho de verdade no IndexedDB, recarreguei a página, confirmei que o modal aparece com a OS certa e que "Continuar" popula o formulário corretamente — não só no jsdom
- [x] **Tela de detalhe do RAD para Supervisor/Administrador (17/07/2026)**: `/consultar/<numero_rad>/` — todos os campos, colaboradores, anexos, exportação (copiar mensagem, baixar PDF, baixar Word — os três batendo direto na API real com o token de autenticação) e cancelamento com confirmação obrigatória (RG-CAN-001 a 012). Listagem em `/consultar/` ganhou filtros (N° RAD, N° SA, status) e os itens agora linkam para o detalhe
  - Antes disso, o Administrador **não tinha nenhuma forma de cancelar um RAD pela interface** — só batendo na API diretamente. Era o maior buraco funcional restante para esse perfil de usuário
  - **Testado com navegador real (Playwright) contra o backend de verdade**, não só mocks: criei um RAD sincronizado de verdade, abri a tela, cliquei em "Baixar PDF" e confirmei que o arquivo baixado começa com `%PDF` de verdade (o `Content-Disposition` do backend funcionando via clique real, não só via `curl`), depois cliquei em "Cancelar", preenchi a justificativa, confirmei, e a página recarregada mostrou o RAD como cancelado — o ciclo completo, ponta a ponta, num Chromium de verdade
  - 12 cenários adicionais com DOM real (jsdom): renderização dos campos, cópia de mensagem, e o fluxo de cancelamento (bloqueio sem justificativa, sucesso com justificativa)
  - **Ainda falta**: gestão de colaboradores (CRUD) pelo Administrador não tem tela própria — hoje só via API
- [x] **Gerenciar Colaboradores para Administrador (18/07/2026)**: `/gerenciar-colaboradores/` — adicionar, editar (registro/nome), ativar/desativar, e excluir definitivamente (com aviso de que RADs já sincronizados guardam cópia própria do nome e não são afetados). Endpoint novo `GET /colaboradores/administrar/`, exclusivo do Administrador — o único jeito de ver colaboradores **inativos** também (a busca usada no formulário do RAD só mostra ativos, de propósito)
- [x] **Importação em lote de colaboradores via CSV (20/07/2026)**: `POST /colaboradores/importar/` — pedido depois que o piloto foi ao ar e a lista real de colaboradores da CPTM se mostrou grande demais para cadastrar um por um. Um colaborador por linha (`registro_empresa,nome`), cabeçalho detectado automaticamente. Trata os problemas reais de planilha brasileira: aceita `;` **ou** `,` como separador (Excel em português normalmente exporta com `;`), decodifica UTF-8 com/sem BOM e cai para Latin-1 se precisar, preserva acentuação. Comportamento **upsert** — quem já existe tem o nome atualizado e é reativado, então a mesma lista pode ser reenviada sempre que a CPTM mandar uma atualização, sem duplicar ninguém. Uma linha com erro (registro não numérico, nome vazio) é reportada com o número da linha, sem travar a importação das demais
  - 13 testes cobrindo separador `;`/`,`, acentuação, upsert, linha inválida no meio do arquivo sem travar o resto, arquivo vazio/grande demais/binário, e uma importação de 500 linhas de uma vez (a escala real do problema relatado)
  - **Testado com navegador real (Playwright) e um arquivo no formato exato que o Excel brasileiro gera** (ponto e vírgula, BOM do Windows, acentos) — confirmei via API de busca que os dados persistiram corretamente no banco, com acentuação intacta
  - Antes disso, não havia **nenhuma** forma de cadastrar, editar ou desativar colaboradores pela interface — só direto na API. Era o maior buraco funcional restante para esse perfil de usuário
  - 12 cenários com DOM real (jsdom): listagem, criar, registro duplicado bloqueado, desativar, editar, excluir com confirmação
  - **Testado com navegador real (Playwright) contra o backend de verdade**: adicionei um colaborador de verdade, confirmei via API que persistiu, desativei pela tela, e confirmei que ele **sumiu da busca usada no formulário de RAD** — a prova de que desativar aqui realmente afeta o fluxo de preenchimento em produção, não só a tela de gestão isoladamente

## Deploy — infraestrutura pronta (18/07/2026)

O que antes era um checklist manual agora é configuração de verdade, testada:

- **Configurações de segurança de produção** em `config/settings.py`, ativadas automaticamente quando `DEBUG=False` (não mexem em nada do ambiente de desenvolvimento): `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS, e `SECURE_PROXY_SSL_HEADER` (necessário atrás de qualquer proxy reverso que termina o TLS antes do Django — Railway, Render, nginx). Testado rodando `check --deploy` nos dois modos: **6 avisos em dev → 0 avisos em produção**
- **`DATABASE_URL` suportado** (`dj-database-url`), com fallback para as variáveis `DB_*` de sempre se não estiver definida — é o padrão usado por Railway, Render e Heroku, então a configuração já funciona **independente de qual desses for escolhido** (decisão de provedor de nuvem ainda pendente, mas deixou de bloquear esta parte)
- **`Dockerfile`** multi-stage, provider-agnóstico — a mesma imagem roda em Railway, Render, AWS ECS/Fargate, Azure Container Apps ou qualquer orquestrador Docker comum. `gunicorn` como servidor WSGI de produção (`runserver` não serve pra isso), `whitenoise` servindo estático com hash+compressão sem precisar de um servidor web separado (só ativo quando `DEBUG=False`, pra não atrapalhar o ciclo normal de desenvolvimento)
- **`docker-compose.yml`** pra testar a imagem localmente antes de mandar pra qualquer nuvem
- **`GET /saude/`** — health check pra orquestrador de container/load balancer, confirma que o banco está acessível de verdade, não só que o processo respondeu
- **`.github/workflows/testes.yml`** — CI rodando a suíte inteira (Python + jsdom + Playwright) a cada push/PR. É específico do GitHub Actions como referência; a decisão de hospedagem do repositório (GitHub x GitLab) ainda está pendente, mas a mesma sequência de passos se traduz direto pra um `.gitlab-ci.yml`

**Bug real pego antes de qualquer produção ver isso**: o `jsPDF` minificado referencia um arquivo `.map` (para debug) que eu não tinha copiado do pacote npm — isso quebra o `collectstatic` **completamente** assim que alguém rodasse o Dockerfile com `DEBUG=False`. Só apareceu porque testei o comando de verdade em modo produção antes de assumir que o Dockerfile funcionava. Corrigido, e travado com um teste que roda `collectstatic` de verdade em modo produção como parte da suíte — provei que ele pega a regressão reintroduzindo o bug de propósito e vendo o teste falhar, antes de restaurar a correção.

⚠️ Não consegui buildar a imagem Docker de verdade nesta sessão (o sandbox onde estou trabalhando não tem Docker instalado) — validei cada peça arriscada individualmente fora do container (o `collectstatic` em modo produção, que é o passo mais frágil), mas o `docker build .` em si ainda não foi executado ponta a ponta. Vale rodar isso antes do primeiro deploy real.

## Checklist antes de ir para produção
Só resta o que exige uma decisão sua, não configuração:
- [ ] `SECRET_KEY` gerada de verdade (não a de exemplo do `.env.example`) — `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- [ ] `ALLOWED_HOSTS` com o domínio real, não `localhost`
- [ ] `DEBUG=False` no `.env`/variáveis de ambiente de produção (o resto — HTTPS, cookies seguros, HSTS — já é automático a partir disso)
- [ ] Rodar `docker build .` de verdade pelo menos uma vez antes do primeiro deploy — não foi testado ponta a ponta nesta sessão (ver aviso acima)

## Decisão técnica registrada: geração do Número de Execução
A EFD descreve o processo com `SELECT ... FOR UPDATE` sobre as linhas existentes da SA. Identificamos que essa abordagem não trava nada quando é a *primeira* ocorrência da SA (nenhuma linha para travar), permitindo corrida entre os dois primeiros RADs concorrentes. Implementamos com `pg_advisory_xact_lock`, que trava pelo valor da SA independentemente de existirem linhas. Ver comentários em `rad/regras_negocio.py` e o teste de concorrência em `rad/test_regras_negocio.py`.

## Pendências que exigem sua decisão (ver briefing)
- ~~Framework CSS (Jazzmin/Unfold + Bootstrap 5)~~ — decisão tomada durante a construção do frontend: design próprio (`interface/static/interface/css/estilo.css`), paleta definida pelo cliente em 17/07/2026, sem depender de Bootstrap ou de admin themes de terceiros
- Provedor de nuvem (Fase 2) — **destravado parcialmente**: o `Dockerfile` roda em qualquer um deles, então a escolha final só afeta configuração de infraestrutura (variáveis de ambiente, banco gerenciado), não código
- Política de segurança para hospedagem do repositório (GitHub x GitLab)
- Via da MCH29U-BFU no seed_cat_mch.sql (segue vazia/TODO)
