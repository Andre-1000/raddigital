-- ============================================================
-- SEED: cat_linhas
-- Sistema RAD — Linhas ferroviárias
-- ============================================================
TRUNCATE TABLE cat_linhas RESTART IDENTITY CASCADE;

INSERT INTO cat_linhas (codigo, nome) VALUES
  ('11', 'Coral'),
  ('12', 'Safira'),
  ('13', 'Jade');

-- Total: 3 registros
