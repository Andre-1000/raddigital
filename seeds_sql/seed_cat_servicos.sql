-- ============================================================
-- SEED: cat_servicos
-- Sistema RAD — Serviços executados (CAT-003)
-- Coluna descricao: texto exibido no botão de ajuda (?)
-- requer_amv: TRUE somente para Manutenção em AMV
-- requer_descricao: TRUE somente para Outros
-- requer_terceiros / terceiros_tem_op_maquina / terceiros_tem_volume
--   (22/07/2026): abrem o bloco "Terceiros" no formulario
-- area (30/07/2026): agrupamento visual em blocos expansíveis na tela
--   de preenchimento — Geral, Infra, Corretiva, Mecanizada.
--
-- Mudanças de negócio 22/07/2026: "Limpeza" e "Controle de Vegetação"
-- foram DESATIVADOS (ativo=FALSE).
-- Mudanças de negócio 30/07/2026: "Esmerilhamento", "Lubrificação",
-- "Socaria" e "Ajuste" foram DESATIVADOS (ativo=FALSE). Adicionados:
-- "Topografia" (grupo Corretiva) e "Esmerilhadora", "Desguarnecedora",
-- "Descarga de lastro", "Socadora" (grupo Mecanizada).
-- Nenhum serviço é removido de verdade do banco — RadServico tem FK
-- PROTECT contra CatServico e RADs antigos podem referenciá-los.
--
-- IMPORTANTE: este seed usa UPSERT (INSERT ... ON CONFLICT), NAO
-- TRUNCATE. Este arquivo roda a cada deploy (start.sh ->
-- carregar_catalogos) -- um TRUNCATE ... CASCADE aqui apagaria em
-- cascata TODOS os RADs ja sincronizados, pois a tabela rad_servicos
-- (e por tabela, rad) tem FK para cat_servicos.
-- ============================================================

INSERT INTO cat_servicos (nome, descricao, requer_amv, requer_descricao, requer_terceiros, terceiros_tem_op_maquina, terceiros_tem_volume, area, ativo) VALUES
  ('Inspeção', 'Verificação visual, dimensional ou geométrica da via permanente, podendo ser realizada a pé ou com veículo. Inclui registro de anomalias, medição de desgaste, avaliação de condições dos componentes e monitoramento geral do estado da via.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', TRUE),
  ('Ajuste', 'Regulagem, reaperto e calibração de elementos da via permanente e de AMVs. Inclui aperto de fixações, ajuste de mecanismos de chave, regulagem de folgas e calibração de dispositivos.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', FALSE),
  ('Limpeza', 'Limpeza e desobstrução de componentes da via permanente. Inclui remoção de detritos, limpeza de canaletas, desobstrução de drenos, limpeza de mecanismos de AMV e remoção de resíduos que comprometam a operação.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', FALSE),
  ('Lubrificação', 'Aplicação de lubrificantes em juntas de trilho, elementos de fixação e partes móveis da via permanente. Executada conforme plano de manutenção ou necessidade identificada em inspeção.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', FALSE),
  ('Substituição', 'Troca parcial ou total de componentes da via permanente em estado degradado. Inclui substituição de trilhos, dormentes, fixações e placas de apoio.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', TRUE),
  ('Reparo', 'Recuperação e conserto de elementos estruturais danificados, sem substituição completa. Inclui correção de defeitos localizados, reparo de fixações e restauração de componentes com dano parcial.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', TRUE),
  ('Soldagem', 'Execução de soldas em trilhos e elementos estruturais da via. Inclui soldagem aluminotérmica, elétrica, reparo de soldas defeituosas e uniões de trilhos.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', TRUE),
  ('Esmerilhamento', 'Retificação da superfície de rolamento dos trilhos. Inclui remoção de ondulações, rebarbas e defeitos superficiais, acabamento de soldas e correção de irregularidades que afetam o conforto de marcha.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', FALSE),
  ('Alinhamento', 'Alinhamento e nivelamento geométrico da via permanente. Inclui correção de desvios horizontais e verticais e restabelecimento dos parâmetros geométricos dentro das tolerâncias operacionais.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', TRUE),
  ('Socaria', 'Socaria mecânica e compactação do lastro para recomposição do apoio dos dormentes. Inclui estabilização da camada de lastro e restauração da geometria da via após intervenções.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', FALSE),
  ('Controle de Vegetação', 'Roçada e poda de vegetação na faixa de domínio e área da via permanente. Inclui remoção de plantas invasoras, limpeza de drenos afetados por vegetação e manutenção da visibilidade operacional.', FALSE, FALSE, FALSE, FALSE, FALSE, 'geral', FALSE),
  ('Manutenção em AMV', 'Manutenção, inspeção e intervenção em Aparelhos de Mudança de Via (AMV). Ao selecionar este serviço, o sistema exibe o bloco AMV, com a possibilidade de adicionar até 16 blocos (uma MCH por bloco): Identificação MCH, Modelo, Via, UR, Local, Linha, Tipo de Defeito e Ações.', TRUE, FALSE, FALSE, FALSE, FALSE, 'amv', TRUE),
  ('Recolhimento de Lixo', 'Recolhimento de lixo e resíduos na faixa de domínio, executado com mão de obra terceirizada. Ao selecionar, o sistema exibe o bloco Terceiros (Encarregados, Op Máquina, Ajudantes, Motorista, Volume).', FALSE, FALSE, TRUE, TRUE, TRUE, 'infra', TRUE),
  ('Limpeza de Canaleta', 'Limpeza de canaletas e drenos, executada com mão de obra terceirizada. Ao selecionar, o sistema exibe o bloco Terceiros (Encarregados, Ajudantes, Motorista, Volume).', FALSE, FALSE, TRUE, FALSE, TRUE, 'infra', TRUE),
  ('Capina Química', 'Aplicação de herbicida para controle de vegetação, executada com mão de obra terceirizada. Ao selecionar, o sistema exibe o bloco Terceiros (Encarregados, Op Máquina, Ajudantes, Motorista).', FALSE, FALSE, TRUE, TRUE, FALSE, 'infra', TRUE),
  ('Roçada/Poda', 'Roçada e poda de vegetação, executada com mão de obra terceirizada. Ao selecionar, o sistema exibe o bloco Terceiros (Encarregados, Op Máquina, Ajudantes, Motorista, Volume).', FALSE, FALSE, TRUE, TRUE, TRUE, 'infra', TRUE),
  ('Topografia', 'Serviço do grupo Corretiva.', FALSE, FALSE, FALSE, FALSE, FALSE, 'corretiva', TRUE),
  ('Esmerilhadora', 'Serviço do grupo Mecanizada.', FALSE, FALSE, FALSE, FALSE, FALSE, 'mecanizada', TRUE),
  ('Desguarnecedora', 'Serviço do grupo Mecanizada.', FALSE, FALSE, FALSE, FALSE, FALSE, 'mecanizada', TRUE),
  ('Descarga de lastro', 'Serviço do grupo Mecanizada.', FALSE, FALSE, FALSE, FALSE, FALSE, 'mecanizada', TRUE),
  ('Socadora', 'Serviço do grupo Mecanizada.', FALSE, FALSE, FALSE, FALSE, FALSE, 'mecanizada', TRUE),
  ('Outros', 'Serviço não contemplado na lista padrão. Ao selecionar esta opção, o sistema exibe automaticamente um campo de texto para descrição do serviço.', FALSE, TRUE, FALSE, FALSE, FALSE, 'geral', TRUE)
ON CONFLICT (nome) DO UPDATE SET
  descricao = EXCLUDED.descricao,
  requer_amv = EXCLUDED.requer_amv,
  requer_descricao = EXCLUDED.requer_descricao,
  requer_terceiros = EXCLUDED.requer_terceiros,
  terceiros_tem_op_maquina = EXCLUDED.terceiros_tem_op_maquina,
  terceiros_tem_volume = EXCLUDED.terceiros_tem_volume,
  area = EXCLUDED.area,
  ativo = EXCLUDED.ativo;

-- Total: 22 registros (6 inativos: Ajuste, Limpeza, Lubrificação,
-- Esmerilhamento, Socaria, Controle de Vegetação)
