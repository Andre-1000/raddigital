-- ============================================================
-- SEED: cat_tipos_manutencao
-- Sistema RAD — Tipos de manutenção
-- ============================================================
TRUNCATE TABLE cat_tipos_manutencao RESTART IDENTITY CASCADE;

INSERT INTO cat_tipos_manutencao (nome) VALUES
  ('Falha'),
  ('Preventiva'),
  ('Corretiva'),
  ('Preditiva');

-- Total: 4 registros
