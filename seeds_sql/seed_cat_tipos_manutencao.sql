-- ============================================================
-- SEED: cat_tipos_manutencao
-- Sistema RAD — Tipos de manutenção
--
-- IMPORTANTE (22/07/2026): UPSERT, NAO TRUNCATE. Roda a cada deploy
-- (start.sh -> carregar_catalogos) -- TRUNCATE ... CASCADE aqui
-- apagaria em cascata TODOS os RADs ja sincronizados (rad tem FK
-- para cat_tipos_manutencao).
-- ============================================================

INSERT INTO cat_tipos_manutencao (nome) VALUES
  ('Falha'),
  ('Preventiva'),
  ('Corretiva'),
  ('Preditiva')
ON CONFLICT (nome) DO NOTHING;

-- Total: 4 registros
