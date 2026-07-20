-- ============================================================
-- SEED: cat_tipos_defeito_amv
-- Sistema RAD — Tipos de defeito do AMV (CAT-010)
-- ============================================================
TRUNCATE TABLE cat_tipos_defeito_amv RESTART IDENTITY CASCADE;

INSERT INTO cat_tipos_defeito_amv (nome, ativo) VALUES
  ('SEM INDICAÇÃO EM NORMAL',          TRUE),
  ('SEM INDICAÇÃO EM REVERSO',         TRUE),
  ('SEM INDICAÇÃO EM AMBOS SENTIDOS',  TRUE),
  ('ATROPELAMENTO',                    TRUE),
  ('MAU CONTATO',                      TRUE),
  ('DESALINHAMENTO',                   TRUE),
  ('DESGASTE',                         TRUE),
  ('ERRO OPERACIONAL',                 TRUE),
  ('AMBIENTE',                         TRUE),
  ('AUSÊNCIA DE ÓLEO',                 TRUE),
  ('ROLETES DANIFICADOS',              TRUE),
  ('CARVÃO TESTACADO',                 TRUE),
  ('MANGUEIRAS DANIFICADAS',           TRUE),
  ('AUSÊNCIA DE GRAXA',                TRUE),
  ('AUSENCIA DE FIXAÇÃO',              TRUE),
  ('RELÉ DP25',                        TRUE),
  ('FISH TAIL TRAVADO',                TRUE);

-- Total: 17 registros
