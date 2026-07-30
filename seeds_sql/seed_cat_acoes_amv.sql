-- ============================================================
-- SEED: cat_acoes_amv
-- Sistema RAD — Ações do AMV (CAT-011)
-- requer_descricao (22/07/2026): TRUE somente para Outros -- abre
-- campo de texto livre no formulario.
--
-- IMPORTANTE: este seed usa UPSERT (INSERT ... ON CONFLICT), NAO
-- TRUNCATE. Este arquivo roda a cada deploy (start.sh ->
-- carregar_catalogos) -- um TRUNCATE ... CASCADE aqui apagaria em
-- cascata TODOS os RADs ja sincronizados com bloco AMV.
-- ============================================================

INSERT INTO cat_acoes_amv (nome, ativo, requer_descricao) VALUES
  ('REPARO DE TERMINAIS',         TRUE, FALSE),
  ('ALINHAMENTO',                  TRUE, FALSE),
  ('SUBSTITUIÇÃO',                 TRUE, FALSE),
  ('COMPLEMENTO DE ÓLEO',          TRUE, FALSE),
  ('LUBRIFICAÇÃO',                 TRUE, FALSE),
  ('REPARO DE ELEMENTOS',          TRUE, FALSE),
  ('DESTRAVAMENTO E LUBRIFICAÇÃO', TRUE, FALSE),
  ('Outros',                       TRUE, TRUE)
ON CONFLICT (nome) DO UPDATE SET
  ativo = EXCLUDED.ativo,
  requer_descricao = EXCLUDED.requer_descricao;

-- Total: 8 registros
