-- ============================================================
-- SEED: cat_equipes
-- Sistema RAD — Equipes envolvidas na atividade
-- Mudanca de negocio (17/07/2026)
--
-- IMPORTANTE (22/07/2026): UPSERT, NAO TRUNCATE. Roda a cada deploy
-- (start.sh -> carregar_catalogos) -- TRUNCATE ... CASCADE aqui
-- apagaria em cascata TODOS os RADs ja sincronizados (rad_equipes ->
-- rad tem FK para cat_equipes).
-- ============================================================

INSERT INTO cat_equipes (codigo, nome) VALUES
  ('RA', 'RA'),
  ('VP', 'VP'),
  ('CIVIL', 'CIVIL'),
  ('RESTAB', 'RESTAB'),
  ('SINAL', 'SINAL'),
  ('MRO', 'MRO')
ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome;

-- Total: 6 registros
