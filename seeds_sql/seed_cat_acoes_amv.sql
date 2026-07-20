-- ============================================================
-- SEED: cat_acoes_amv
-- Sistema RAD — Ações do AMV (CAT-011)
-- ============================================================
TRUNCATE TABLE cat_acoes_amv RESTART IDENTITY CASCADE;

INSERT INTO cat_acoes_amv (nome, ativo) VALUES
  ('REPARO DE TERMINAIS',         TRUE),
  ('ALINHAMENTO',                  TRUE),
  ('SUBSTITUIÇÃO',                 TRUE),
  ('COMPLEMENTO DE ÓLEO',          TRUE),
  ('LUBRIFICAÇÃO',                 TRUE),
  ('REPARO DE ELEMENTOS',          TRUE),
  ('DESTRAVAMENTO E LUBRIFICAÇÃO', TRUE);

-- Total: 7 registros
