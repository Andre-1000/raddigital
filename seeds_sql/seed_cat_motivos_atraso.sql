-- ============================================================
-- SEED: cat_motivos_atraso
-- Sistema RAD — Motivos de atraso de início e término
--
-- IMPORTANTE (22/07/2026): UPSERT, NAO TRUNCATE. Roda a cada deploy
-- (start.sh -> carregar_catalogos) -- TRUNCATE ... CASCADE aqui
-- apagaria em cascata TODOS os RADs ja sincronizados (rad tem FK
-- para cat_motivos_atraso).
-- ============================================================

INSERT INTO cat_motivos_atraso (nome, requer_descricao) VALUES
  ('Comunicação com CCO', FALSE),
  ('Trânsito',            FALSE),
  ('Clima',               FALSE),
  ('Outros',              TRUE)
ON CONFLICT (nome) DO UPDATE SET requer_descricao = EXCLUDED.requer_descricao;

-- Total: 4 registros
