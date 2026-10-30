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

- `catalogos`: até `0014_limite_blocos_amv.py`
- `rad`: até `0029_operador_cco_ccm.py`
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

## Autenticação — histórico e estado atual

- **30/07/2026 (resolvido):** o login passou a exigir senha de verdade. Antes disso,
  qualquer requisição com um login existente no banco recebia token válido de 7 dias
  sem provar identidade nenhuma (achado 🔴 de auditoria informal contra OWASP Top
  10:2025, com implicação de LGPD). Hoje `usuarios/views.py::login` verifica senha
  por hash (PBKDF2), com rate limit por tentativas (`MAXIMO_TENTATIVAS_LOGIN`,
  `BLOQUEIO_LOGIN_MINUTOS`) e mensagem de erro genérica (evita enumeração de conta).
- **28/09/2026:** o login passou a aceitar **somente a matrícula** (campo `login` do
  model `Usuario`) — deixou de aceitar e-mail. O e-mail continua existindo no
  cadastro, mas fica reservado exclusivamente para o fluxo de "Esqueci minha senha"
  (`usuarios/views.py::solicitar_redefinicao_senha`), que não mudou.
- `usuarios/tests.py::TestLogin` está desatualizado desde 30/07/2026 — os testes
  fazem login sem enviar senha, então falham contra o `login()` atual. O projeto não
  roda essa suíte automaticamente (ver "O que NÃO fazer" abaixo), então isso não
  bloqueia deploy, mas os testes mentem se alguém rodar `pytest` esperando que
  passem. Ainda não corrigido — avisar André se o assunto de testes voltar à tona.

## Edição de RAD pelo Administrador (13/10/2026)

O Administrador pode editar um RAD já sincronizado (botão "Editar este RAD" no
detalhe → `/consultar/<numero_rad>/editar/`). Decisões que não devem ser desfeitas
sem combinar com o André:
- Edita NO LUGAR (mesmo `numero_rad`), qualquer campo, passando pelas MESMAS
  validações de um RAD novo (`rad/edicao.py::editar_rad` reaproveita
  `validar_payload_sincronizacao` e `regras_negocio.montar_dados_rad`).
- **Motivo obrigatório** e **histórico** (`RadEdicao`: quem, quando, motivo, antes/depois
  por campo). RAD cancelado não é editável.
- Foto "removida" é **ocultada** (`RadAnexo.oculto`), nunca apagada. O manager padrão
  `RadAnexo.objects` já exclui os ocultos (tudo que lê `rad.anexos` os ignora);
  `RadAnexo.todos` enxerga todos.
- Editar **não reenvia nada sozinho**: só preenche `Rad.data_ultima_edicao`. Drive e
  planilha ficam "desatualizados" (`Rad.drive_desatualizado` / `planilha_desatualizada`)
  até o reenvio MANUAL — "Salvar no Drive" troca o conteúdo do arquivo existente
  (`google_drive.substituir_docx_no_drive`, sem criar cópia) e o Sync BD atualiza a
  linha existente pela coluna A (`google_sheets.atualizar_linhas`). Motivo: gerar o Word
  com fotos é o passo mais pesado de memória (Render 512MB).
- Trocou a OS → novo `numero_execucao` na OS nova (maior existente + 1); a OS antiga
  fica com "buraco". `regras_negocio.proxima_execucao_da_os` usa MAIOR+1 (não contagem+1)
  justamente por isso.
- A tela de edição é o mesmo `novo_rad.html` + `rad_form.js` em modo edição
  (`window.RAD_EDICAO`); nesse modo nada é lido/gravado no IndexedDB.

## Tipo "Falha" não tem horário programado (14/10/2026)
- Tipo de Manutenção = Falha: Horário Programado de Início/Término (e datas) ficam **ocultos/desabilitados** na tela e são guardados **NULL** no banco (migration `0028_horarios_programados_opcionais`). `duracao_programada_min` e `data_hora_prog_*` também NULL.
- Horários reais continuam obrigatórios; duração real continua calculada; atraso continua desligado para Falha.
- Backend: `regras_horario.processar_horarios` (Falha → prog = None), `regras_negocio._preparar_horarios`/`montar_dados_rad`, VLD-011 e `_CONDICAO_VISIBILIDADE_CAMPO_CONFIG` (config "obrigatório" não trava Falha).
- Qualquer código novo que leia `hora_prog_*`/`duracao_programada_min` DEVE tratar `None` (exportações usam "N/A").
- Frontend: `rad_form.js::atualizarHorariosProgramadosPorTipo` (usa atributo `hidden`, não `style.display`, para não colidir com Configurações); `ExportarCliente.camposObrigatorios*(rascunho, ehFalha)`.
- Testes: `rad/test_falha_sem_horario_programado.py`, `interface/js_tests/teste_falha_horarios.js`.

## Bloco "Inspeção e Ronda" em Serviços Executados (14/10/2026)
- Nova área `insp_ronda` (rótulo "Inspeção e Ronda") com os serviços "Inspeção" e
  "Reparo" (simples, sem bloco extra, limite de fotos padrão). Em 15/10/2026 entrou
  também "Pedido de Interdição" (simples, só pelo seed — sem migration).
- Os antigos "Inspeção" e "Reparo" do Geral foram **renomeados** para "Inspeção (Geral)"
  e "Reparo (Geral)" e **desativados** (migration `catalogos/0013_inspecao_e_ronda`).
  Os ~112 RADs antigos continuam apontando para eles (histórico intacto no Geral);
  André vai reclassificar caso a caso os que forem de ronda.
- Edição de RAD: `GET /rad/<n>/dados-edicao/` devolve `servicos_desativados` (serviços
  inativos que o RAD usa) e `rad_form.js` os mostra com "(desativado)" para o
  Administrador poder desmarcar/trocar. Antes disso, um serviço desativado ficava
  marcado e invisível na edição.
- Testes: `rad/test_inspecao_e_ronda.py`, `interface/js_tests/teste_inspecao_ronda.js`.
- Consulta (15/10/2026): o filtro "Serviço executado → Subcategoria" lista também os
  serviços **desativados**, com "(desativado)", no fim de cada área — para achar os RADs
  antigos. Vem de `GET /catalogos/todos/?incluir_servicos_desativados=1`, na chave
  separada `servicos_desativados`; a chave `servicos` continua só com ativos porque o
  formulário a guarda offline. Testes: `consulta/test_filtro_servico_desativado.py`,
  `interface/js_tests/teste_consulta_servico_desativado.js`.

## Mensagem "Copiar" (WhatsApp) por grupos (26/10/2026)
- Vale **só para a mensagem**; PDF e Word continuam usando `_campos_do_relatorio`/`montarCampos`
  sem mudança (o Word oficial tem `{{ATIVIDADE}}` = resumo da descrição técnica, outra coisa).
- Grupos com título em negrito + emoji (Identificação, Datas e Horários, Localização,
  Execução, Responsáveis, Descrição Técnica, Observação Geral), linha em branco entre eles,
  sem as linhas `___`.
- Campo que se aplica mas está vazio → rótulo sem valor (`Solicitante SA:`), nunca "N/A".
  Campo que não se aplica → não aparece: N° Falha só em Falha; Programado só fora de Falha;
  Motivo dos atrasos só com atraso no término (o formulário não pede motivo de início);
  Descrição de Outros só com "Outros"; Terceiros só se o serviço pede. Campo desabilitado
  pelo Administrador some (o celular recebe a lista em `catalogos.campos_desabilitados`).
- Pares explícitos: `09:30 (início) // 15:30 (término)`, `SGU (inicial) // PTR (final)`.
- "Atividade" saiu (repetia "Serviços realizados"); entraram Tipo de Manutenção, Tipo de
  Veículo e Operador. Campo com rótulo junta quebras de linha com vírgula; texto livre mantém.
- Dois geradores que DEVEM ficar iguais: `rad/exportacao.py::gerar_mensagem_copiar`
  (Consulta) e `exportar_cliente.js::gerarMensagemCopiar` (celular/offline). O teste
  `rad/test_mensagem_whatsapp.py::TestServidorIgualCelular` compara os dois textos.

## OS e N° SA com regra fixa (29/10/2026)
- Bug real: OS marcada como opcional em Configurações deixava o RAD passar sem OS e o banco
  recusava (coluna NOT NULL; o Nº de execução vem da OS) → erro 500 na sincronização.
- **OS obrigatória em todo RAD.** **N° SA conforme o Tipo de Manutenção:** obrigatória em
  Preventiva/Preditiva (`TIPOS_MANUTENCAO_QUE_EXIGEM_SA` em `rad/validadores.py`), opcional
  nos demais (Corretiva…), **inativa em Falha** — SA e Solicitante SA desabilitados e limpos
  na tela, gravados vazios no servidor (`regras_negocio.montar_dados_rad`), mesmo que o
  cliente mande valor. Flag `_tipo_manutencao_exige_sa` no payload de validação (sincronizar
  e editar).
- Regra fixa: `configuracoes.servicos.CAMPOS_REGRA_FIXA` = {numero_os, numero_sa}. Saíram de
  `_MAPA_CHAVE_CONFIG_PARA_CAMPO_PAYLOAD`; `campos_desabilitados()` os ignora; a API de
  Configurações devolve `regra_fixa: true` (sempre habilitado/obrigatório) e recusa
  alterá-los (409); a tela mostra o aviso no lugar dos botões.
- Tela: bloco **Controle Operacional vem antes de Identificação** (o tipo decide a SA).
  `rad_form.js::atualizarSaPorTipo`; `ExportarCliente.camposObrigatorios*(rascunho, ehFalha, exigeSa)`.
- Exportações: Word `{{SA}}` vazio → "N/A"; mensagem WhatsApp não mostra SA/Solicitante em Falha.
- Testes: `rad/test_os_sa_regra_fixa.py`, `interface/js_tests/teste_os_sa_regra_fixa.js`.

## Manutenção Corretiva em AMV e Operador CCO/CCM (30/10/2026)
- Serviço novo **"Manutenção Corretiva em AMV"** no bloco Corretiva (só pelo seed, num
  INSERT próprio no fim de `seed_cat_servicos.sql`): abre o Bloco AMV com as mesmas regras
  de "Manutenção em AMV", mas no máximo **3 blocos** (1 + 2 pelo botão). Campo
  `CatServico.limite_blocos_amv` (migration `catalogos/0014`; vazio = 16). Com os dois
  serviços marcados vale o **maior** limite. `rad/validadores.py::limite_blocos_amv` e
  `rad_form.js::limiteBlocosAmv`. Acima do limite a tela avisa e não apaga nada.
- **Operador CCO/CCM** (antes "Op CCM"): Abertura e Entrega ganham a escolha CCO ou CCM
  (`Rad.operador_ccm_abertura_centro`/`_entrega_centro`, migration `rad/0029`, opcional).
  Dois "flegues" exclusivos ("Opção 1 - CCO" / "Opção 2 - CCM"); a Entrega copia a Abertura
  até ser mexida. Textos: "Fulano (08:00) – CCO" (mensagem, PDF/Word simples, Word oficial
  na Abertura). A migration renomeia os rótulos em Configurações. Planilha/Excel não têm
  colunas de operador (nem antes) — nada a mudar no cabeçalho.
- Testes: `rad/test_amv_corretiva_e_cco_ccm.py`, `interface/js_tests/teste_amv_corretiva_cco_ccm.js`.

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
  Exceção: campos de regra fixa (`CAMPOS_REGRA_FIXA` — hoje OS e N° SA) não entram no mapa.
- Serviços do catálogo (`CatServico`) têm campo `area` (`amv`/`corretiva`/`geral`/
  `infra`/`insp_ronda`/`mecanizada`, máx. 10 caracteres) usado só pra agrupamento
  visual em blocos expansíveis na tela de preenchimento — não afeta regra de negócio,
  exceto Infra, que também controla limite de fotos (ver
  `configuracoes.models.LimiteFotos`). Os blocos aparecem em **ordem alfabética do
  rótulo** (desde 14/10/2026) — `AREA_CHOICES` já está nessa ordem e o JS ordena pelo
  rótulo; área nova precisa entrar em `AREA_CHOICES`, `ROTULOS_GRUPO_SERVICO`
  (`rad_form.js`), `ROTULO_AREA`/`ROTULO_AREA_GRAFICO` (`dashboard.js`) e no
  `<select>`/`ROTULO_AREA` de `consulta.html`.
- Renomear um serviço existente (ex.: "Recolhimento de Lixo" → "Recolhimento de
  Descartes") deve ser uma migration `RunPython` que faz `update(nome=...)` na MESMA
  linha — nunca desativar uma e criar outra, isso quebraria a FK de RADs antigos.

## Fotos no Word oficial (28/10/2026)
- Bug real (R00459, erro 500 ao baixar o Word): foto JPEG com EXIF defeituoso abre no Pillow
  (passa na sincronização), mas o python-docx lê o EXIF sozinho e quebra
  (`UnexpectedEndOfFileError`). Correção em `rad/exportacao_oficial.py::_normalizar_foto_para_word`:
  o Pillow regrava cada foto como JPEG limpo, sem EXIF, já girada (`exif_transpose`) e
  reduzida a `LADO_MAXIMO_FOTO_PX` (1600). Foto ilegível vira aviso em texto na célula;
  nunca derruba o Word inteiro. Vale também para "Salvar no Drive" (mesmo gerador).
- Testes: `rad/test_word_foto_exif.py`.

## Logs (28/10/2026)
- `LOGGING` em `config/settings.py`: todo erro 500 escreve o traceback completo na saída
  do processo (Render → Logs), formato `[data] ERROR django.request: ...`. Antes não havia
  configuração e, com `DEBUG=False`, o Django escondia o erro (só aparecia "... 500 145").
- Nível geral pela variável de ambiente opcional `LOG_LEVEL` (padrão `WARNING`).
- Teste: `config/test_logging.py` (roda um processo com `DEBUG=False`, como em produção).

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
  MCH"; "Manutenção Corretiva em AMV" = até 3), cada um com MCH/Tipo de Defeito/Ações próprios. `RadAmv` é FK normal pro
  Rad (não mais `OneToOneField`); `RadAmvDefeito`/`RadAmvAcao` apontam pro **bloco**
  (`RadAmv`), não mais direto pro RAD.
- **Operador CCO/CCM** (era "Operador CCM"): 6 campos (`operador_ccm_abertura_nome/hora/centro`,
  `operador_ccm_entrega_nome/hora/centro`). Nome e centro da Abertura auto-preenchem a
  Entrega, editável depois (para de sincronizar assim que editado manualmente).
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
