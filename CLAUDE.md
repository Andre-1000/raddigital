# CLAUDE.md — Sistema RAD Digital

Contexto que a Claude deve carregar no início de qualquer conversa sobre este projeto.

## O que é o projeto

RAD Digital: PWA offline-first em Django + PostgreSQL, para técnicos de manutenção
ferroviária (CPTM/TRIVIA — linhas 11-Coral, 12-Safira, 13-Jade) preencherem RADs
(Relatório de Atividade Diária) em campo, substituindo um processo informal via WhatsApp.

- **Repo:** `github.com/Andre-1000/raddigital`, branch `main`
- **Live:** raddigital.onrender.com (Render, plano free)
- **Path local:** `C:\Users\andre.junior\Documents\Desenvolvimento de RAD Digital\projeto_rad_sistema_RAD\projeto_rad`

## Fluxo de trabalho (importante — ler antes de gerar qualquer arquivo)

André não usa Claude Code — trabalha aqui no chat. O conector Git é **só leitura**
(`create_or_update_file`/`push_files` retornam 403 mesmo com o app GitHub configurado
com `contents: write` e reinstalado do zero — já foi investigado a fundo, **não vale
tentar de novo**, é limitação do lado do serviço). Fluxo:

1. Claude busca os arquivos atuais do repo via `Git:get_file_contents` antes de editar
   (nunca supor conteúdo de memória — arquivos mudam entre conversas).
2. Claude gera **arquivos completos prontos pra substituir** — nunca snippets, nunca
   instruções de find-and-replace.
3. André baixa, substitui no caminho local correspondente, e roda:
   ```
   git add . && git commit -m "..." && git push origin main
   ```
4. Push na `main` dispara auto-deploy no Render (`start.sh`: migrate → carregar
   catálogos → gunicorn).

Sempre que gerar uma alteração, listar claramente **arquivo → pasta de destino**.

### Testar migrations que reestruturam dado existente

Pra mudanças de banco que mexem em relacionamento entre tabelas já existentes (não
só `AddField`), vale instalar Postgres local + clonar o repo real (`git clone` do
GitHub funciona, é só a escrita que não funciona) + rodar as migrations até o ponto
exato de produção + inserir dados de teste simulando RADs já sincronizados + aplicar
a migration nova + verificar integridade + **testar a reversão também**
(`migrate app 000X` pra trás). Esse processo já achou e evitou 2 bugs reais antes de
irem pra produção: um `AttributeError` de reversão quebrada (coluna `NOT NULL`
recriada sem dado) e um drift de metadado (`help_text`/`Meta.options` sem migration
correspondente, pego com `makemigrations --check --dry-run`).

## Stack e estrutura

Django (apps: `usuarios`, `catalogos`, `rad`, `consulta`, `colaboradores`,
`configuracoes`, `interface`, `comum`) + PostgreSQL + frontend vanilla JS/HTML com
IndexedDB (offline-first, sem framework front-end).

- Frontend: `interface/static/interface/js/` (JS puro) e
  `interface/templates/interface/` (templates Django).
- `rad_form.js` é o maior arquivo do projeto (~1700 linhas) — normal ser grande,
  não é sinal de que precisa ser dividido.
- Cores do tema: `#242472` navy, `#fa5e13` orange, `#11aa60` green, `#fffcff`
  quase-branco, `#b8300f` perigo.

## Estado das migrations (conferir antes de criar a próxima)

- `catalogos`: até `0011_inspecoes_e_renomeacao.py`
- `rad`: até `0014_multiplos_blocos_amv.py`
- `configuracoes`: até `0006_limite_fotos.py`

## Regras críticas — nunca violar

1. **Seeds SQL (`seeds_sql/*.sql`) usam sempre UPSERT (`INSERT ... ON CONFLICT`),
   nunca `TRUNCATE`.** Rodam a CADA deploy via `carregar_catalogos`. Um
   `TRUNCATE ... CASCADE` apagaria em cascata todos os RADs já sincronizados.
2. **Toda migration nova vai na pasta do app certo** (`<app>/migrations/`). Verificar
   o número da última migration existente antes de criar a próxima — ver seção acima.
3. **Campo novo em catálogo (`CatServico`, `CatLocal`, etc.) precisa refletir no
   seed correspondente**, senão o `INSERT` falha com `NotNullViolation` e trava o
   deploy inteiro.
4. **Fotos ficam no Cloudflare R2** (`django-storages`), nunca no disco do Render
   (efêmero, apaga a cada deploy). Tier grátis é permanente/recorrente (10GB/mês),
   não é trial de 12 meses como AWS S3.
5. **Render free = 512MB RAM, sem disco persistente, dorme após 15min.** LibreOffice
   não está instalado — exportação em PDF oficial fica atrás de um interruptor em
   Configurações, desligado até o servidor mudar de plano.
6. **Banco Postgres do Render expira 30 dias após criado + 14 dias de carência,
   depois apaga tudo permanentemente, sem backup.** Verificar data em
   dashboard.render.com → raddigital-db → Info. Migração de infraestrutura (Azure,
   dado que a empresa está adotando Microsoft) foi pedida à TI, ainda sem resposta.
7. Nomes de tabela/coluna em `catalogos/models.py` e `rad/models.py` seguem
   exatamente os arquivos seed — não renomear um lado sem o outro.

## ⚠️ Achado de segurança pendente (30/07/2026) — prioridade alta

Auditoria informal contra OWASP Top 10:2025 encontrou que o login
(`usuarios/views.py::login`) **não usa senha nenhuma** — qualquer requisição com um
login existente no banco recebe token válido de 7 dias na hora. Logins seguem padrão
`nome.sobrenome` (previsível), sem rate limit. É o único achado 🔴 da auditoria e tem
implicação de LGPD (dado pessoal de colaboradores exposto por autenticação fraca).
André ainda não decidiu implementar senha/PIN — perguntar sobre isso se o assunto de
segurança voltar à tona, não presumir que já foi resolvido.

## Convenções de código

- Comentários e docstrings em português, sem acentos em identificadores de código
  (mas com acentos em textos exibidos ao usuário, ex.: `"Não foi possível..."`).
- Docstrings de módulo/função explicam o *porquê* de decisões não óbvias, não só o *o quê*.
- Migrations de dados usam `RunPython` com função de reversão simétrica, mesmo
  quando a reversão é só aproximada.
- Validações de sincronização (`rad/validadores.py`) sempre acumulam erros numa
  lista e retornam todos de uma vez (nunca param no primeiro erro).
- Campo condicional (só aparece/é relevante sob certa condição, ex.: N° Falha só
  quando Tipo de Manutenção = Falha) que também pode ser forçado obrigatório pelo
  Administrador precisa de entrada em `_CONDICAO_VISIBILIDADE_CAMPO_CONFIG`
  (`rad/validadores.py`) — senão o toggle "Obrigatório" trava a sincronização mesmo
  com o campo oculto (bug real, já corrigido uma vez).
- Todo campo do formulário que pode ser tornado obrigatório/opcional ou
  habilitado/desabilitado pelo Administrador passa pelo mapa em
  `_MAPA_CHAVE_CONFIG_PARA_CAMPO_PAYLOAD` (`rad/validadores.py`).
- Serviços do catálogo (`CatServico`) têm campo `area` (`geral`/`infra`/`corretiva`/
  `mecanizada`/`amv`) usado só pra agrupamento visual em blocos expansíveis na tela
  de preenchimento — não afeta regra de negócio, exceto Infra, que também controla
  limite de fotos (ver `configuracoes.models.LimiteFotos`).
- Renomear um serviço existente (ex.: "Recolhimento de Lixo" → "Recolhimento de
  Descartes") deve ser uma migration `RunPython` que faz `update(nome=...)` na MESMA
  linha — nunca desativar uma e criar outra, isso quebraria a FK de RADs antigos.

## Gaps conhecidos no Word oficial (`rad/templates_export/rda_oficial_template.docx`)

Não são bugs, são funcionalidades que existem no sistema mas ainda não têm token/
espaço no molde Word — se o assunto de exportação Word voltar, checar se algum destes
já foi resolvido antes de reexplicar do zero:
- Fotos além de 4 (RADs de área Infra têm até 10) — só as 4 primeiras aparecem.
- Blocos AMV (múltiplos, ver abaixo) — nenhum detalhe de MCH/defeito/ação aparece.
- Entrega do Operador CCM — só a Abertura tem campo no molde.
- Colaboradores (nomes/matrículas) — sem seção no molde.

## Funcionalidades grandes já implementadas (pra não redescobrir do zero)

- **Múltiplos blocos AMV por RAD**: até 16 (1 inicial + 15 via botão "Adicionar
  MCH"), cada um com MCH/Tipo de Defeito/Ações próprios. `RadAmv` é FK normal pro
  Rad (não mais `OneToOneField`); `RadAmvDefeito`/`RadAmvAcao` apontam pro **bloco**
  (`RadAmv`), não mais direto pro RAD.
- **Operador CCM**: 4 campos (`operador_ccm_abertura_nome/hora`,
  `operador_ccm_entrega_nome/hora`). Nome da Abertura auto-preenche a Entrega,
  editável depois (para de sincronizar assim que editado manualmente).
- **Limite de fotos configurável por área** (`configuracoes.models.LimiteFotos`,
  tela Configurações → "Limites de Fotos"): padrão 2+2 (4 total), Infra 5+5 (10
  total). Client relê o limite certo ao marcar/desmarcar serviço Infra.
- **Comentários das fotos** (`desc_foto_1..4`): botões "Foto 1-4" no bloco Anexos,
  cada um abre/fecha uma caixa de texto. Obrigatórios (todos, travados abertos)
  quando Tipo de Manutenção = VPM001; opcionais e independentes fora isso.

## Como ajudar André a aprender

André está aprendendo programação do zero (Python/Django). Preferências dele:
- Respostas diretas e curtas; só se aprofundar se ele não entender.
- Sempre mostrar o **impacto** de decisões técnicas, não só a decisão em si.
- Analogias ajudam. Perguntas de verificação ao final de explicações técnicas
  ajudam a fixar o conteúdo.
- Ele dita por voz às vezes — texto pode ter artefatos de transcrição; interpretar
  pelo contexto em vez de pedir para repetir.

## O que NÃO fazer

- Não sugerir stack diferente (FastAPI, SQLAlchemy, pydantic) — o projeto é Django
  e a decisão já foi tomada.
- Não impor limite arbitrário de linhas por arquivo.
- Não pedir para rodar comandos de teste automatizado como pré-requisito de toda
  mudança pequena — o projeto não tem suíte Pytest estabelecida.
- Não usar o conector Git para tentar escrever no repo — é só leitura; sempre
  gerar arquivo pronto para download. Não gastar tempo tentando reconectar/
  reinstalar o app achando que vai destravar escrita — já foi tentado à exaustão.
- Não presumir que o achado de segurança (login sem senha) já foi resolvido sem
  confirmar com André.
