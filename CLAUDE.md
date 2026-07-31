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
(`create_or_update_file`/`push_files` retornam 403). Fluxo:

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

## Stack e estrutura

Django (apps: `usuarios`, `catalogos`, `rad`, `consulta`, `colaboradores`,
`configuracoes`, `interface`, `comum`) + PostgreSQL + frontend vanilla JS/HTML com
IndexedDB (offline-first, sem framework front-end).

- Frontend: `interface/static/interface/js/` (JS puro) e
  `interface/templates/interface/` (templates Django).
- `rad_form.js` é o maior arquivo do projeto (~1400 linhas) — normal ser grande,
  não é sinal de que precisa ser dividido.
- Cores do tema: `#242472` navy, `#fa5e13` orange, `#11aa60` green, `#fffcff`
  quase-branco, `#b8300f` perigo.

## Regras críticas — nunca violar

1. **Seeds SQL (`seeds_sql/*.sql`) usam sempre UPSERT (`INSERT ... ON CONFLICT`),
   nunca `TRUNCATE`.** Esses arquivos rodam a CADA deploy via `carregar_catalogos`.
   Um `TRUNCATE ... CASCADE` apagaria em cascata todos os RADs já sincronizados —
   já aconteceu esse bug uma vez, corrigido.
2. **Toda migration nova vai na pasta do app certo** (`<app>/migrations/`). Verificar
   o número da última migration existente antes de criar a próxima (não confiar em
   número de memória — conferir com `Git:get_file_contents` no diretório de migrations).
3. **Campo novo em catálogo (`CatServico`, `CatLocal`, etc.) precisa refletir no
   seed correspondente**, senão o `INSERT` falha com `NotNullViolation` e trava o
   deploy inteiro.
4. **Fotos ficam no Cloudflare R2** (`django-storages`), nunca no disco do Render
   (efêmero, apaga a cada deploy).
5. **Render free = 512MB RAM, sem disco persistente, dorme após 15min.** LibreOffice
   não está instalado — exportação em PDF oficial fica atrás de um interruptor em
   Configurações, desligado até o servidor mudar de plano.
6. Nomes de tabela/coluna em `catalogos/models.py` e `rad/models.py` seguem
   exatamente os arquivos seed — não renomear um lado sem o outro.

## Convenções de código

- Comentários e docstrings em português, sem acentos em identificadores de código
  (mas com acentos em textos exibidos ao usuário, ex.: `"Não foi possível..."`).
- Docstrings de módulo/função explicam o *porquê* de decisões não óbvias, não só o *o quê*
  (ex.: por que UPSERT em vez de TRUNCATE, por que um lock advisory em vez de FOR UPDATE).
- Migrations de dados usam `RunPython` com função de reversão simétrica, mesmo
  quando a reversão é só aproximada — nunca deixar `migrations.RunPython.noop`
  como reversão se dá pra fazer melhor.
- Validações de sincronização (`rad/validadores.py`) sempre acumulam erros numa
  lista e retornam todos de uma vez (nunca param no primeiro erro).
- Todo campo do formulário que pode ser tornado obrigatório/opcional ou
  habilitado/desabilitado pelo Administrador passa pelo mapa em
  `_MAPA_CHAVE_CONFIG_PARA_CAMPO_PAYLOAD` (`rad/validadores.py`) — ao adicionar um
  campo novo simples, adicionar essa entrada também.

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
  mudança — o projeto não tem suíte Pytest estabelecida ainda; funcionalidade
  crítica (regras de horário, validadores) tem testes, mas não é exigido para
  toda alteração pequena.
- Não usar o conector Git para tentar escrever no repo — ele é só leitura; sempre
  gerar arquivo pronto para download.
