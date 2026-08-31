-- ============================================================
-- SEED: cat_locais
-- Sistema RAD — Locais disponíveis (CAT-002)
-- Total: 72 locais (42 ativos: estações + pátios; 30 inativos:
-- cabines, subestações, terminais, VSE, ALMOX -- desativados em
-- 22/07/2026, ver rad, colaboradores desta decisao)
-- Categorias: estacao, patio, cabine, subestacao, terminal, vse, almox
-- Nota: Terminais usam siglas prefixadas TM para evitar conflito
--       com siglas de estações de mesmo código (DBO, JBO, GUA)
--
-- IMPORTANTE (22/07/2026): este seed usa UPSERT (INSERT ... ON
-- CONFLICT), NAO TRUNCATE. Este arquivo roda a cada deploy
-- (start.sh -> carregar_catalogos) -- um TRUNCATE ... CASCADE aqui
-- apagaria em cascata TODOS os RADs ja sincronizados, pois a tabela
-- rad tem FK para cat_locais. UPSERT atualiza os dados sem destruir
-- nada que dependa desta tabela.
--
-- 27/08/2026: adicionados SGU (Eng. Sebastião Gualberto) e ETR
-- (Eng. Trindade), como estacoes ativas -- pedido direto do cliente.
-- ============================================================

INSERT INTO cat_locais (sigla, nome, categoria, ativo) VALUES
  ('BFU', 'Barra Funda', 'estacao', TRUE),
  ('LUZ', 'Luz', 'estacao', TRUE),
  ('BAS', 'Brás', 'estacao', TRUE),
  ('CCO', 'CCO Brás', 'estacao', TRUE),
  ('TAT', 'Tatuapé', 'estacao', TRUE),
  ('ITQ', 'Itaquera', 'estacao', TRUE),
  ('DBO', 'Dom Bosco', 'estacao', TRUE),
  ('JBO', 'José Bonifácio', 'estacao', TRUE),
  ('GUA', 'Guaianazes', 'estacao', TRUE),
  ('AGN', 'Antônio Gianetti Neto', 'estacao', TRUE),
  ('FVC', 'Ferraz de Vasconcelos', 'estacao', TRUE),
  ('POÁ', 'Poá', 'estacao', TRUE),
  ('CVN', 'Calmon Viana', 'estacao', TRUE),
  ('SUZ', 'Suzano', 'estacao', TRUE),
  ('JPB', 'Jundiapeba', 'estacao', TRUE),
  ('BCB', 'Braz Cubas', 'estacao', TRUE),
  ('MDC', 'Mogi das Cruzes', 'estacao', TRUE),
  ('EST', 'Estudantes', 'estacao', TRUE),
  ('USL', 'Usp Leste', 'estacao', TRUE),
  ('ERM', 'Comendador Ermelino', 'estacao', TRUE),
  ('SMP', 'São Miguel Paulista', 'estacao', TRUE),
  ('JHE', 'Jardim Helena', 'estacao', TRUE),
  ('ITI', 'Itaim Paulista', 'estacao', TRUE),
  ('JRO', 'Jardim Romano', 'estacao', TRUE),
  ('EMF', 'Eng. Manoel Feio', 'estacao', TRUE),
  ('IQC', 'Itaquaquecetuba', 'estacao', TRUE),
  ('ARC', 'Aracaré', 'estacao', TRUE),
  ('EGO', 'Eng. Goulart', 'estacao', TRUE),
  ('GCE', 'Guarulhos CECAP', 'estacao', TRUE),
  ('AGU', 'Aeroporto Guarulhos', 'estacao', TRUE),
  ('SGU', 'Eng. Sebastião Gualberto', 'estacao', TRUE),
  ('ETR', 'Eng. Trindade', 'estacao', TRUE),
  ('PAT 001', 'Patio Luz', 'patio', TRUE),
  ('PAT 003', 'Patio Eng São Paulo', 'patio', TRUE),
  ('PAT 005', 'Patio para Lastros e Dormentes', 'patio', TRUE),
  ('PAT 006', 'Vias de Estacionamento Guaianazes', 'patio', TRUE),
  ('PAT 007', 'Estaleiro TLS', 'patio', TRUE),
  ('PAT 008', 'Lavador de Trem', 'patio', TRUE),
  ('PAT 009', 'Patio Mogi das Cruzes', 'patio', TRUE),
  ('PAT 011', 'Base de Manutenção - Metalurgia e AMVs', 'patio', TRUE),
  ('PAT 013', 'Patio Eng Manoel Feio', 'patio', TRUE),
  ('PAT 014', 'Patio Calmon Viana', 'patio', TRUE),
  ('CSFVA', 'Ferraz de Vasconcelos', 'cabine', FALSE),
  ('CSGUA', 'Guaianazes', 'cabine', FALSE),
  ('CSALV', 'Arthur Alvim', 'cabine', FALSE),
  ('CSVTD', 'Carlos de Campos - Vila Matilde', 'cabine', FALSE),
  ('CSJBO', 'José Bonifácio', 'cabine', FALSE),
  ('CSJPB', 'Jundiapeba', 'cabine', FALSE),
  ('CSEST', 'Estudantes', 'cabine', FALSE),
  ('CSITQ', 'Itaquaquecetuba', 'cabine', FALSE),
  ('CSITI', 'Itaim Paulista', 'cabine', FALSE),
  ('CSBAS', 'Brás', 'cabine', FALSE),
  ('CSEGO', 'Eng. Goulart', 'cabine', FALSE),
  ('CSCEC', 'Guarulhos CECAP', 'cabine', FALSE),
  ('SEDBO', 'Dom Bosco', 'subestacao', FALSE),
  ('SEPTR', 'Patriarca', 'subestacao', FALSE),
  ('SECVN', 'Calmon Viana', 'subestacao', FALSE),
  ('SEBCB', 'Braz Cubas', 'subestacao', FALSE),
  ('SEMAL', 'Memorial da America Latina', 'subestacao', FALSE),
  ('SEGUA', 'Guaianazes', 'subestacao', FALSE),
  ('SEEMF', 'Manoel Feio', 'subestacao', FALSE),
  ('SESGU', 'Sebastiao Gualberto (Patio)', 'subestacao', FALSE),
  ('SEERM', 'C. Ermelino Matarazzo', 'subestacao', FALSE),
  ('SEEGO', 'Eng. Goulart', 'subestacao', FALSE),
  ('SEISP', 'Eng. São Paulo', 'subestacao', FALSE),
  ('SEAGU', 'Aeroporto', 'subestacao', FALSE),
  ('SEAYS', 'Ayrton Senna', 'subestacao', FALSE),
  ('TMDBO', 'Estação Dom Bosco', 'terminal', FALSE),
  ('TMJBO', 'Estação José Bonifácio', 'terminal', FALSE),
  ('TMGUA', 'Estação Guaianazes', 'terminal', FALSE),
  ('VSE', 'R. Alayde de Souza Costa, 234 - Itaquera', 'vse', FALSE),
  ('ALMOX', 'Av. Francisco Rodrigues Filho, 121 - Vila Mogilar', 'almox', FALSE)
ON CONFLICT (sigla) DO UPDATE SET
  nome = EXCLUDED.nome,
  categoria = EXCLUDED.categoria,
  ativo = EXCLUDED.ativo;

-- Total: 72 registros (42 ativos, 30 inativos)
