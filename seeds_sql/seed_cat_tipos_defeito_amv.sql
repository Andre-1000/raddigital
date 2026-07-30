-- ============================================================
-- SEED: cat_tipos_defeito_amv
-- Sistema RAD — Tipos de defeito do AMV (CAT-010)
-- requer_descricao (22/07/2026): TRUE somente para Outros -- abre
-- campo de texto livre no formulario.
--
-- IMPORTANTE: este seed usa UPSERT (INSERT ... ON CONFLICT), NAO
-- TRUNCATE. Este arquivo roda a cada deploy (start.sh ->
-- carregar_catalogos) -- um TRUNCATE ... CASCADE aqui apagaria em
-- cascata TODOS os RADs ja sincronizados com bloco AMV.
-- ============================================================

INSERT INTO cat_tipos_defeito_amv (nome, ativo, requer_descricao) VALUES
  ('SEM INDICAÇÃO EM NORMAL',          TRUE, FALSE),
  ('SEM INDICAÇÃO EM REVERSO',         TRUE, FALSE),
  ('SEM INDICAÇÃO EM AMBOS SENTIDOS',  TRUE, FALSE),
  ('ATROPELAMENTO',                    TRUE, FALSE),
  ('MAU CONTATO',                      TRUE, FALSE),
  ('DESALINHAMENTO',                   TRUE, FALSE),
  ('DESGASTE',                         TRUE, FALSE),
  ('ERRO OPERACIONAL',                 TRUE, FALSE),
  ('AMBIENTE',                         TRUE, FALSE),
  ('AUSÊNCIA DE ÓLEO',                 TRUE, FALSE),
  ('ROLETES DANIFICADOS',              TRUE, FALSE),
  ('CARVÃO TESTACADO',                 TRUE, FALSE),
  ('MANGUEIRAS DANIFICADAS',           TRUE, FALSE),
  ('AUSÊNCIA DE GRAXA',                TRUE, FALSE),
  ('AUSENCIA DE FIXAÇÃO',              TRUE, FALSE),
  ('RELÉ DP25',                        TRUE, FALSE),
  ('FISH TAIL TRAVADO',                TRUE, FALSE),
  ('Outros',                           TRUE, TRUE)
ON CONFLICT (nome) DO UPDATE SET
  ativo = EXCLUDED.ativo,
  requer_descricao = EXCLUDED.requer_descricao;

-- Total: 18 registros
