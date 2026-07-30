-- ============================================================
-- SEED: cat_linhas
-- Sistema RAD — Linhas ferroviárias
--
-- IMPORTANTE (22/07/2026): UPSERT, NAO TRUNCATE. Roda a cada deploy
-- (start.sh -> carregar_catalogos) -- TRUNCATE ... CASCADE aqui
-- apagaria em cascata TODOS os RADs ja sincronizados (rad_linhas ->
-- rad tem FK para cat_linhas).
-- ============================================================

INSERT INTO cat_linhas (codigo, nome) VALUES
  ('11', 'Coral'),
  ('12', 'Safira'),
  ('13', 'Jade')
ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome;

-- Total: 3 registros
