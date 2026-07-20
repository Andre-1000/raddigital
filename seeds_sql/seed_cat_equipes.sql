-- ============================================================
-- SEED: cat_equipes
-- Sistema RAD — Equipes envolvidas na atividade
-- Mudanca de negocio (17/07/2026)
-- ============================================================
TRUNCATE TABLE cat_equipes RESTART IDENTITY CASCADE;

INSERT INTO cat_equipes (codigo, nome) VALUES
  ('RA', 'RA'),
  ('VP', 'VP'),
  ('CIVIL', 'CIVIL'),
  ('RESTAB', 'RESTAB'),
  ('SINAL', 'SINAL'),
  ('MRO', 'MRO');

-- Total: 6 registros
