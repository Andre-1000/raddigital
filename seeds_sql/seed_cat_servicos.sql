-- ============================================================
-- SEED: cat_servicos
-- Sistema RAD — Serviços executados (CAT-003)
-- Total: 13 serviços
-- Coluna descricao: texto exibido no botão de ajuda (?)
-- requer_amv: TRUE somente para Manutenção em AMV
-- requer_descricao: TRUE somente para Outros
-- ============================================================
TRUNCATE TABLE cat_servicos RESTART IDENTITY CASCADE;

INSERT INTO cat_servicos (nome, descricao, requer_amv, requer_descricao, ativo) VALUES
  ('Inspeção', 'Verificação visual, dimensional ou geométrica da via permanente, podendo ser realizada a pé ou com veículo. Inclui registro de anomalias, medição de desgaste, avaliação de condições dos componentes e monitoramento geral do estado da via.', FALSE, FALSE, TRUE),
  ('Ajuste', 'Regulagem, reaperto e calibração de elementos da via permanente e de AMVs. Inclui aperto de fixações, ajuste de mecanismos de chave, regulagem de folgas e calibração de dispositivos.', FALSE, FALSE, TRUE),
  ('Limpeza', 'Limpeza e desobstrução de componentes da via permanente. Inclui remoção de detritos, limpeza de canaletas, desobstrução de drenos, limpeza de mecanismos de AMV e remoção de resíduos que comprometam a operação.', FALSE, FALSE, TRUE),
  ('Lubrificação', 'Aplicação de lubrificantes em juntas de trilho, elementos de fixação e partes móveis da via permanente. Executada conforme plano de manutenção ou necessidade identificada em inspeção.', FALSE, FALSE, TRUE),
  ('Substituição', 'Troca parcial ou total de componentes da via permanente em estado degradado. Inclui substituição de trilhos, dormentes, fixações e placas de apoio.', FALSE, FALSE, TRUE),
  ('Reparo', 'Recuperação e conserto de elementos estruturais danificados, sem substituição completa. Inclui correção de defeitos localizados, reparo de fixações e restauração de componentes com dano parcial.', FALSE, FALSE, TRUE),
  ('Soldagem', 'Execução de soldas em trilhos e elementos estruturais da via. Inclui soldagem aluminotérmica, elétrica, reparo de soldas defeituosas e uniões de trilhos.', FALSE, FALSE, TRUE),
  ('Esmerilhamento', 'Retificação da superfície de rolamento dos trilhos. Inclui remoção de ondulações, rebarbas e defeitos superficiais, acabamento de soldas e correção de irregularidades que afetam o conforto de marcha.', FALSE, FALSE, TRUE),
  ('Alinhamento', 'Alinhamento e nivelamento geométrico da via permanente. Inclui correção de desvios horizontais e verticais e restabelecimento dos parâmetros geométricos dentro das tolerâncias operacionais.', FALSE, FALSE, TRUE),
  ('Socaria', 'Socaria mecânica e compactação do lastro para recomposição do apoio dos dormentes. Inclui estabilização da camada de lastro e restauração da geometria da via após intervenções.', FALSE, FALSE, TRUE),
  ('Controle de Vegetação', 'Roçada e poda de vegetação na faixa de domínio e área da via permanente. Inclui remoção de plantas invasoras, limpeza de drenos afetados por vegetação e manutenção da visibilidade operacional.', FALSE, FALSE, TRUE),
  ('Manutenção em AMV', 'Manutenção, inspeção e intervenção em Aparelhos de Mudança de Via (AMV). Ao selecionar este serviço, o sistema exibe automaticamente o bloco AMV com campos adicionais: Identificação MCH, Modelo, Via, UR, Local, Linha, Tipo de Defeito e Ações.', TRUE, FALSE, TRUE),
  ('Outros', 'Serviço não contemplado na lista padrão. Ao selecionar esta opção, o sistema exibe automaticamente um campo de texto para descrição do serviço.', FALSE, TRUE, TRUE);

-- Total: 13 registros
