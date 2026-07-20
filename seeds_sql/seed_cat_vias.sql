-- ============================================================
-- SEED: cat_vias
-- Sistema RAD — Vias disponíveis para seleção
-- ============================================================
TRUNCATE TABLE cat_vias RESTART IDENTITY CASCADE;

INSERT INTO cat_vias (nome) VALUES
  ('Via 1'),
  ('Via 2'),
  ('Via 3'),
  ('Via 4'),
  ('Pátio');

-- Total: 5 registros
