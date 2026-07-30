-- ============================================================
-- SEED: cat_vias
-- Sistema RAD — Vias disponíveis para seleção
--
-- IMPORTANTE (22/07/2026): UPSERT, NAO TRUNCATE. Roda a cada deploy
-- (start.sh -> carregar_catalogos) -- TRUNCATE ... CASCADE aqui
-- apagaria em cascata TODOS os RADs ja sincronizados (rad_vias ->
-- rad tem FK para cat_vias).
-- ============================================================

INSERT INTO cat_vias (nome) VALUES
  ('Via 1'),
  ('Via 2'),
  ('Via 3'),
  ('Via 4'),
  ('Pátio')
ON CONFLICT (nome) DO NOTHING;

-- Total: 5 registros
