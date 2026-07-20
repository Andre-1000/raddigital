# Notas de Layout do Formulário RAD (para a fase de frontend)

Este arquivo registra decisões de UI/UX combinadas durante o backend,
que não têm onde "morar" no código ainda porque o formulário de
preenchimento do RAD (cliente offline-first) não foi construído. Deve
ser consultado quando a fase de frontend começar, e as regras aqui
devem ser conferidas/removidas conforme forem implementadas.

## Anexos (fotos e PDF)

- Fotos divididas em **dois grupos com identificação visual clara** de
  que são coisas diferentes (não uma lista única misturada):
  - **"Intervenção verificada"** — até 2 fotos.
  - **"Ação realizada"** — até 2 fotos.
- Total: 4 fotos + 1 PDF por RAD.
- Backend já reflete isso: `RadAnexo.categoria_foto`, campos de upload
  separados `fotos_intervencao_verificada` e `fotos_acao_realizada`
  (ver `rad/views.py::sincronizar`, `rad/validadores_arquivos.py`).

## Exportação (PDF / Copiar msg) — RESOLVIDO (17/07/2026)

**Decisão final do cliente**: o template original (estrutura da EFD seção 3.13) **não muda**, mas todos os campos adicionados nas mudanças de negócio recentes precisam aparecer nele. Implementado em `rad/exportacao.py`:

- `gerar_mensagem_copiar(rad)` — mesmo formato de campo:valor da EFD 3.13, com os campos novos inseridos (OS, N° SA, Equipes Envolvidas, Responsável Atividade, Operador CCM, Descrição Técnica da Atividade).
- `gerar_pdf_bytes(rad)` e `gerar_docx_bytes(rad)` — PDF (reportlab) e Word (python-docx), ambos os formatos exigidos por RG-EXP-003, mesma lista de campos (fonte única, nunca divergem entre si nem da mensagem).
- Ambos respeitam o recurso de desabilitar campos (app `configuracoes`) — campo desabilitado não aparece em nenhum dos dois.
- Endpoints: `GET /consulta/rads/<numero_rad>/mensagem/`, `/pdf/` e `/docx/`, acessíveis ao Supervisor, Administrador, ou ao próprio técnico que criou o RAD.

**Nota de arquitetura**: a EFD descreve a exportação como ação client-side/offline, pré-sincronização (RG-EXP-002/011). Esta implementação (backend) atende à consulta pós-sincronização. A exportação client-side/offline pré-sync foi implementada em 18/07/2026 em `interface/static/interface/js/exportar_cliente.js`, reaproveitando exatamente a mesma lista/ordem de campos desta implementação — testado campo a campo para garantir que nunca divergem.

## Ordem dos campos no formulário — RESOLVIDO (17/07/2026)

- O campo **"Observações Gerais"** fica **abaixo** do bloco de
  fotos/anexos no formulário de preenchimento de RAD (rascunho local,
  antes da sincronização). Implementado em `interface/templates/interface/novo_rad.html`
  e travado por teste posicional (`interface/js_tests/teste_campos_finais.js`).
- Isso é sobre o **formulário de preenchimento** apenas. A exportação
  (PDF/Copiar msg) já foi resolvida acima e usa a estrutura original da
  EFD 3.13 — "Observação Geral" já é o último campo lá, então nenhuma
  reordenação foi necessária na exportação.

## Ação pendente ao retomar a fase de frontend — TUDO FEITO (18/07/2026)

1. ~~Ao construir a tela de preenchimento, aplicar a ordem de campos
   acima (Observações Gerais abaixo dos anexos).~~ Feito.
2. ~~Ao construir a exportação client-side/offline (RG-EXP-002), reusar
   `rad/exportacao.py::_campos_do_relatorio` como referência de campos
   e ordem — já validado e testado no backend.~~ Feito — ver
   `interface/static/interface/js/exportar_cliente.js`.
