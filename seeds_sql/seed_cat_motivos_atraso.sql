-- ============================================================
-- SEED: cat_motivos_atraso
-- Sistema RAD — Motivos de atraso de início e término
-- ============================================================
TRUNCATE TABLE cat_motivos_atraso RESTART IDENTITY CASCADE;

INSERT INTO cat_motivos_atraso (nome, requer_descricao) VALUES
  ('Comunicação com CCO', FALSE),
  ('Trânsito',            FALSE),
  ('Clima',               FALSE),
  ('Outros',              TRUE);

-- Total: 4 registros
