/*
 * ExportarCliente — exportacao 100% offline, direto do rascunho local
 * (RG-EXP-001 a 010), sem depender do servidor.
 *
 * Mesma lista de campos que rad/exportacao.py::_campos_do_relatorio no
 * backend (mesma ordem, mesmos rotulos) -- a diferenca e que aqui os
 * valores vem do rascunho local (IDs) resolvidos contra os catalogos
 * cacheados no IndexedDB, em vez de vir de um Rad ja salvo no banco.
 * Quando o backend ganhar suporte a template oficial (RG-EXP-007,
 * pendente do cliente), esta lista deve ser atualizada nos dois
 * lugares juntos.
 */
const ExportarCliente = (function () {
  const NAO_APLICAVEL = 'N/A';

  function ouNA(valor) {
    if (valor === null || valor === undefined || valor === '') return NAO_APLICAVEL;
    return String(valor);
  }

  function listaOuNA(valores) {
    return valores && valores.length ? valores.join(', ') : NAO_APLICAVEL;
  }

  // 30/10/2026: acrescenta CCO/CCM ao texto do operador -- "Fulano (08:00)
  // – CCO"; so o centro, sem nome: "CCO". Mesmo formato do servidor
  // (rad/exportacao.py::_com_centro).
  function comCentro(texto, centro) {
    if (!centro) return texto;
    if (!texto || texto === NAO_APLICAVEL) return centro;
    return `${texto} – ${centro}`;
  }

  function nomePorCodigo(catalogo, campoCodigo, codigo) {
    const item = catalogo.find((c) => String(c[campoCodigo]) === String(codigo));
    return item ? item.nome : null;
  }

  function montarCampos(rascunho, catalogos) {
    const local = function (sigla) {
      const item = catalogos.locais.find((l) => l.sigla === sigla);
      return item ? item.sigla : sigla;
    };

    const nomesLinhas = (rascunho.linhas || []).map(
      (codigo) => nomePorCodigo(catalogos.linhas, 'codigo', codigo) || codigo
    );
    const nomesVias = (rascunho.vias || []).map(
      (id) => nomePorCodigo(catalogos.vias, 'id', id) || id
    );
    const nomesEquipes = (rascunho.equipes || []).map(
      (codigo) => nomePorCodigo(catalogos.equipes, 'codigo', codigo) || codigo
    );
    const nomesServicos = (rascunho.servicos || []).map(
      (id) => nomePorCodigo(catalogos.servicos, 'id', id) || id
    );
    let textoServicos = nomesServicos.length ? nomesServicos.join(', ') : NAO_APLICAVEL;
    if (rascunho.outros_servico_desc) {
      textoServicos += ` (${rascunho.outros_servico_desc})`;
    }

    const nomesColaboradores = (rascunho.colaboradores || []).map((p) => p.nome);

    // 30/09/2026: as linhas de Terceiros so entram quando algum dos
    // servicos SELECIONADOS pede aquele dado -- mesma regra que o
    // formulario ja usa pra mostrar ou esconder cada campo (ver
    // rad_form.js::atualizarVisibilidadeServicos). Antes, as 5 linhas
    // apareciam sempre (como "N/A") em qualquer RAD, mesmo sem nenhum
    // servico de Terceiros selecionado (ex.: so "Manutencao em AMV").
    //   - Encarregados/Ajudantes/Motorista: servico com requer_terceiros.
    //   - Op Maquina: servico com terceiros_tem_op_maquina.
    //   - Volume: servico com terceiros_tem_volume.
    const servicosSelecionados = (catalogos.servicos || []).filter(
      (s) => (rascunho.servicos || []).includes(s.id)
    );
    function algumServicoTem(flag) {
      return servicosSelecionados.some((s) => s[flag]);
    }
    const mostrarTerceiros = algumServicoTem('requer_terceiros');
    const mostrarOpMaquina = algumServicoTem('terceiros_tem_op_maquina');
    const mostrarVolume = algumServicoTem('terceiros_tem_volume');

    const partesAtraso = [];
    if (rascunho.id_motivo_atraso_inicio) {
      let motivo = nomePorCodigo(catalogos.motivos_atraso, 'id', rascunho.id_motivo_atraso_inicio);
      if (rascunho.desc_motivo_atraso_inicio) motivo += `: ${rascunho.desc_motivo_atraso_inicio}`;
      partesAtraso.push(`Início — ${motivo}`);
    }
    if (rascunho.id_motivo_atraso_termino) {
      let motivo = nomePorCodigo(catalogos.motivos_atraso, 'id', rascunho.id_motivo_atraso_termino);
      if (rascunho.desc_motivo_atraso_termino) motivo += `: ${rascunho.desc_motivo_atraso_termino}`;
      partesAtraso.push(`Término — ${motivo}`);
    }
    const textoMotivoAtrasos = partesAtraso.length ? partesAtraso.join('; ') : NAO_APLICAVEL;

    // 30/07/2026: Operador CCM agora e dois pares Nome+Hora
    // (Abertura/Entrega). Sem nome, o par inteiro cai em N/A -- a hora
    // sozinha (mesmo com o default 00:00) nao tem sentido sem nome.
    function textoOperadorCcm(nome, hora, centro) {
      return comCentro(nome ? `${nome} (${ouNA(hora)})` : NAO_APLICAVEL, centro);
    }

    return [
      ['servicos', 'Atividade', textoServicos],
      // 05/09/2026: "Data" passou a usar Data da Atividade (pedido do
      // cliente, mesma troca feita no Word oficial) -- Data de
      // Preenchimento continua aparecendo, agora como linha propria,
      // ja que aqui (diferente do molde do Word) nao ha limite de 1
      // unico campo de data.
      ['data_atividade', 'Data da Atividade', formatarDataBr(rascunho.data_atividade)],
      ['data_preenchimento', 'Data de Preenchimento', formatarDataBr(rascunho.data_preenchimento)],
      ['numero_os', 'OS', ouNA(rascunho.numero_os)],
      ['numero_sa', 'N° SA', ouNA(rascunho.numero_sa)],
      ['solicitante_sa', 'Solicitante SA', ouNA(rascunho.solicitante_sa)],
      ['numero_falha', 'Falha', ouNA(rascunho.numero_falha)],
      ['local_inicial', 'Local', `${local(rascunho.id_local_inicial)}/${local(rascunho.id_local_final)}`],
      ['linhas', 'Linha', listaOuNA(nomesLinhas)],
      ['vias', 'Via', listaOuNA(nomesVias)],
      ['equipes', 'Equipes Envolvidas', listaOuNA(nomesEquipes)],
      ['km_poste_inicial', 'Km/Poste Inicial', ouNA(rascunho.km_poste_inicial)],
      ['km_poste_final', 'Km/Poste Final', ouNA(rascunho.km_poste_final)],
      [
        'hora_prog_inicio', 'Horário programado',
        // Falha: sem horario programado (campos vazios) -> N/A inteiro.
        rascunho.hora_prog_inicio || rascunho.hora_prog_termino
          ? `${ouNA(rascunho.hora_prog_inicio)} a ${ouNA(rascunho.hora_prog_termino)}`
          : NAO_APLICAVEL,
      ],
      ['hora_real_inicio', 'Início', ouNA(rascunho.hora_real_inicio)],
      ['hora_real_termino', 'Término', ouNA(rascunho.hora_real_termino)],
      ['servicos', 'Serviços realizados', textoServicos], // duplicado, igual ao backend (EFD 3.13)
      ...(mostrarTerceiros
        ? [['terceiros_num_encarregados', 'N° Encarregados (Terceiros)', ouNA(rascunho.terceiros_num_encarregados)]]
        : []),
      ...(mostrarOpMaquina
        ? [['terceiros_num_op_maquina', 'N° Op Máquina (Terceiros)', ouNA(rascunho.terceiros_num_op_maquina)]]
        : []),
      ...(mostrarTerceiros
        ? [
            ['terceiros_num_ajudantes', 'N° Ajudantes (Terceiros)', ouNA(rascunho.terceiros_num_ajudantes)],
            ['terceiros_num_motorista', 'N° Motorista (Terceiros)', ouNA(rascunho.terceiros_num_motorista)],
          ]
        : []),
      ...(mostrarVolume
        ? [['terceiros_volume', 'Volume (Terceiros)', ouNA(rascunho.terceiros_volume)]]
        : []),
      ['materiais_utilizados', 'Equipamentos utilizados', ouNA(rascunho.materiais_utilizados)],
      ['motivo_atraso_inicio', 'Motivo dos atrasos', textoMotivoAtrasos],
      ['colaboradores', 'Responsável', listaOuNA(nomesColaboradores)],
      ['responsavel_atividade', 'Responsável Atividade', ouNA(rascunho.responsavel_atividade)],
      ['tipo_veiculo', 'Tipo de Veículo', ouNA(rascunho.tipo_veiculo)],
      ['operador', 'Operador', ouNA(rascunho.operador)],
      [
        'operador_ccm_abertura', 'Operador CCO/CCM - Abertura',
        textoOperadorCcm(rascunho.operador_ccm_abertura_nome, rascunho.operador_ccm_abertura_hora, rascunho.operador_ccm_abertura_centro),
      ],
      [
        'operador_ccm_entrega', 'Operador CCO/CCM - Entrega',
        textoOperadorCcm(rascunho.operador_ccm_entrega_nome, rascunho.operador_ccm_entrega_hora, rascunho.operador_ccm_entrega_centro),
      ],
      ['descricao_tecnica_atividade', 'Descrição Técnica da Atividade', ouNA(rascunho.descricao_tecnica_atividade)],
      ['observacoes_gerais', 'Observação Geral', ouNA(rascunho.observacoes_gerais)],
    ];
  }

  function formatarDataBr(dataIso) {
    if (!dataIso) return NAO_APLICAVEL;
    const [ano, mes, dia] = dataIso.split('-');
    return `${dia}/${mes}/${ano}`;
  }

  // -------------------------------------------------------------------
  // Mensagem "Copiar" para o WhatsApp -- formato por grupos (26/10/2026).
  // MESMO formato de rad/exportacao.py::gerar_mensagem_copiar (servidor);
  // mudar os dois juntos. Regras (decisao do Andre):
  //   - sem "___": grupos com titulo em negrito + emoji, linha em branco
  //     entre grupos;
  //   - campo que se aplica mas esta vazio: rotulo sem valor ("Falha:");
  //   - campo que nao se aplica (N° Falha fora de Falha, Programado em
  //     Falha, Terceiros sem servico que peca, etc.): nao aparece;
  //   - pares: "09:30 (início) // 15:30 (término)";
  //   - "Atividade" saiu (repetia "Serviços realizados").
  // PDF e Word offline continuam usando montarCampos, sem mudanca.
  // -------------------------------------------------------------------
  const TITULO_MENSAGEM = '*RAD – Relatório de Atividade Diária*';

  function vazioSeNada(valor) {
    if (valor === null || valor === undefined) return '';
    return String(valor).trim();
  }

  function par(primeiro, segundo, rotulo1, rotulo2) {
    const a = vazioSeNada(primeiro);
    const b = vazioSeNada(segundo);
    if (!a && !b) return '';
    return `${a || '—'} (${rotulo1}) // ${b || '—'} (${rotulo2})`;
  }

  function gruposDaMensagem(rascunho, catalogos) {
    const nomeTipo = nomePorCodigo(catalogos.tipos_manutencao || [], 'id', rascunho.id_tipo_manutencao) || '';
    const ehFalha = nomeTipo === 'Falha';
    const servicosSel = (catalogos.servicos || []).filter((s) => (rascunho.servicos || []).includes(s.id));
    const nomesServicos = (rascunho.servicos || []).map((id) => nomePorCodigo(catalogos.servicos || [], 'id', id) || id);
    const temOutros = servicosSel.some((s) => s.nome === 'Outros');
    const pede = (flag) => servicosSel.some((s) => s[flag]);
    const nomes = (lista, catalogo, campo) =>
      (lista || []).map((codigo) => nomePorCodigo(catalogo || [], campo, codigo) || codigo).join(', ');
    const dataBr = (iso) => (iso ? formatarDataBr(iso) : '');
    const ccm = (nome, hora) => {
      const n = vazioSeNada(nome);
      if (!n) return '';
      return hora ? `${n} (${hora})` : n;
    };

    const identificacao = [
      ['tipo_manutencao', 'Tipo de Manutenção', nomeTipo],
      ['numero_os', 'OS', rascunho.numero_os],
    ];
    if (!ehFalha) { // 29/10/2026: SA e Solicitante SA ficam inativos em Falha
      identificacao.push(
        ['numero_sa', 'N° SA', rascunho.numero_sa],
        ['solicitante_sa', 'Solicitante SA', rascunho.solicitante_sa]
      );
    }
    if (ehFalha) identificacao.push(['numero_falha', 'N° Falha', rascunho.numero_falha]);

    const datas = [
      ['data_atividade', 'Data da Atividade', dataBr(rascunho.data_atividade)],
      ['data_preenchimento', 'Data de Preenchimento', dataBr(rascunho.data_preenchimento)],
    ];
    if (!ehFalha) {
      datas.push(['hora_prog_inicio', 'Programado', par(rascunho.hora_prog_inicio, rascunho.hora_prog_termino, 'início', 'término')]);
    }
    datas.push(['hora_real_inicio', 'Realizado', par(rascunho.hora_real_inicio, rascunho.hora_real_termino, 'início', 'término')]);
    // No rascunho o atraso e calculado na tela (nao ha flag guardada) e o
    // motivo e limpo quando nao ha atraso -- entao motivo preenchido =
    // houve atraso. (No servidor a regra usa Rad.atraso_inicio/termino.)
    if (rascunho.id_motivo_atraso_inicio || rascunho.id_motivo_atraso_termino) {
      const partes = [];
      if (rascunho.id_motivo_atraso_inicio) {
        let m = nomePorCodigo(catalogos.motivos_atraso || [], 'id', rascunho.id_motivo_atraso_inicio) || '';
        if (rascunho.desc_motivo_atraso_inicio) m += `: ${rascunho.desc_motivo_atraso_inicio}`;
        partes.push(`Início — ${m}`);
      }
      if (rascunho.id_motivo_atraso_termino) {
        let m = nomePorCodigo(catalogos.motivos_atraso || [], 'id', rascunho.id_motivo_atraso_termino) || '';
        if (rascunho.desc_motivo_atraso_termino) m += `: ${rascunho.desc_motivo_atraso_termino}`;
        partes.push(`Término — ${m}`);
      }
      datas.push(['motivo_atraso_inicio', 'Motivo dos atrasos', partes.join('; ')]);
    }

    const localizacao = [
      ['local_inicial', 'Local', par(rascunho.id_local_inicial, rascunho.id_local_final, 'inicial', 'final')],
      ['linhas', 'Linha', nomes(rascunho.linhas, catalogos.linhas, 'codigo')],
      ['vias', 'Via', nomes(rascunho.vias, catalogos.vias, 'id')],
      ['km_poste', 'Km/Poste', par(rascunho.km_poste_inicial, rascunho.km_poste_final, 'inicial', 'final')],
    ];

    const execucao = [
      ['equipes', 'Equipes Envolvidas', nomes(rascunho.equipes, catalogos.equipes, 'codigo')],
      ['servicos', 'Serviços realizados', nomesServicos.join(', ')],
    ];
    if (temOutros) execucao.push(['outros_servico_desc', 'Descrição de Outros', rascunho.outros_servico_desc]);
    if (pede('requer_terceiros')) execucao.push(['terceiros', 'N° Encarregados (Terceiros)', rascunho.terceiros_num_encarregados]);
    if (pede('terceiros_tem_op_maquina')) execucao.push(['terceiros', 'N° Op Máquina (Terceiros)', rascunho.terceiros_num_op_maquina]);
    if (pede('requer_terceiros')) {
      execucao.push(['terceiros', 'N° Ajudantes (Terceiros)', rascunho.terceiros_num_ajudantes]);
      execucao.push(['terceiros', 'N° Motorista (Terceiros)', rascunho.terceiros_num_motorista]);
    }
    if (pede('terceiros_tem_volume')) execucao.push(['terceiros', 'Volume (Terceiros)', rascunho.terceiros_volume]);
    execucao.push(
      ['materiais_utilizados', 'Equipamentos utilizados', rascunho.materiais_utilizados],
      ['tipo_veiculo', 'Tipo de Veículo', rascunho.tipo_veiculo],
      ['operador', 'Operador', rascunho.operador]
    );

    const responsaveis = [
      ['colaboradores', 'Responsável', (rascunho.colaboradores || []).map((p) => p.nome).join(', ')],
      ['responsavel_atividade', 'Responsável Atividade', rascunho.responsavel_atividade],
      ['operador_ccm_abertura', 'Operador CCO/CCM - Abertura', comCentro(ccm(rascunho.operador_ccm_abertura_nome, rascunho.operador_ccm_abertura_hora), rascunho.operador_ccm_abertura_centro)],
      ['operador_ccm_entrega', 'Operador CCO/CCM - Entrega', comCentro(ccm(rascunho.operador_ccm_entrega_nome, rascunho.operador_ccm_entrega_hora), rascunho.operador_ccm_entrega_centro)],
    ];

    return [
      ['📋 *IDENTIFICAÇÃO*', identificacao],
      ['📅 *DATAS E HORÁRIOS*', datas],
      ['📍 *LOCALIZAÇÃO*', localizacao],
      ['🛠️ *EXECUÇÃO*', execucao],
      ['👷 *RESPONSÁVEIS*', responsaveis],
      ['📝 *DESCRIÇÃO TÉCNICA*', [['descricao_tecnica_atividade', null, rascunho.descricao_tecnica_atividade]]],
      ['💬 *OBSERVAÇÃO GERAL*', [['observacoes_gerais', null, rascunho.observacoes_gerais]]],
    ];
  }

  function gerarMensagemCopiar(rascunho, catalogos) {
    // Campos desabilitados pelo Administrador (rad_form.js passa a lista
    // em catalogos.campos_desabilitados) somem, igual ao servidor.
    const desabilitados = new Set((catalogos && catalogos.campos_desabilitados) || []);
    const blocos = [TITULO_MENSAGEM];
    gruposDaMensagem(rascunho, catalogos).forEach(function ([titulo, itens]) {
      const linhas = [];
      itens.forEach(function ([chave, rotulo, valor]) {
        if (desabilitados.has(chave)) return;
        let texto = vazioSeNada(valor);
        if (rotulo !== null) {
          // Campo com rotulo: quebra de linha viraria uma linha "solta" que
          // parece outro campo -- junta com virgula (texto livre mantem).
          texto = texto.split(/\r?\n/).map((p) => p.trim()).filter(Boolean).join(', ');
        }
        linhas.push(rotulo === null ? texto : `${rotulo}: ${texto}`.trimEnd());
      });
      if (linhas.length) blocos.push([titulo, ...linhas].join('\n'));
    });
    return blocos.join('\n\n');
  }

  function gerarPdfBlob(rascunho, catalogos) {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ unit: 'mm', format: 'a4' });
    const campos = montarCampos(rascunho, catalogos);

    doc.setFontSize(16);
    doc.text('RAD — Relatório de Atividade Diária', 15, 18);
    doc.setFontSize(10);
    doc.text('Rascunho local — ainda não sincronizado', 15, 25);

    let y = 35;
    doc.setFontSize(11);
    campos.forEach(function ([_chave, rotulo, valor]) {
      if (y > 280) {
        doc.addPage();
        y = 20;
      }
      doc.setFont(undefined, 'bold');
      doc.text(`${rotulo}:`, 15, y);
      doc.setFont(undefined, 'normal');
      const linhas = doc.splitTextToSize(String(valor), 130);
      doc.text(linhas, 65, y);
      y += 6 * Math.max(linhas.length, 1);
    });

    return doc.output('blob');
  }

  function gerarDocxBlob(rascunho, catalogos) {
    const campos = montarCampos(rascunho, catalogos);
    const linhasTabela = campos
      .map(
        ([_chave, rotulo, valor]) =>
          `<tr><td style="padding:4px 8px;"><b>${escaparHtml(rotulo)}</b></td><td style="padding:4px 8px;">${escaparHtml(String(valor))}</td></tr>`
      )
      .join('');

    const html = `
      <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
      <head><meta charset="utf-8"><title>RAD</title></head>
      <body>
        <h1>RAD — Relatório de Atividade Diária</h1>
        <p><i>Rascunho local — ainda não sincronizado</i></p>
        <table border="1" cellspacing="0" style="border-collapse:collapse; width:100%;">
          ${linhasTabela}
        </table>
      </body>
      </html>
    `;
    return new Blob(['\ufeff', html], { type: 'application/msword' });
  }

  function escaparHtml(texto) {
    const div = document.createElement('div');
    div.textContent = texto;
    return div.innerHTML;
  }

  const CAMPOS_OBRIGATORIOS_ROTULOS = [
    ['numero_os', 'OS'],
    ['numero_sa', 'N° SA'],
    ['data_preenchimento', 'Data de Preenchimento'],
    ['data_atividade', 'Data da Atividade'],
    ['id_local_inicial', 'Local Inicial'],
    ['id_local_final', 'Local Final'],
    ['km_poste_inicial', 'Km/Poste Inicial'],
    ['km_poste_final', 'Km/Poste Final'],
    ['linhas', 'Linha'],
    ['vias', 'Via'],
    ['id_tipo_manutencao', 'Tipo de Manutenção'],
    ['hora_prog_inicio', 'Horário Programado de Início'],
    ['hora_prog_termino', 'Horário Programado de Término'],
    ['hora_real_inicio', 'Horário Real de Início'],
    ['hora_real_termino', 'Horário Real de Término'],
    ['servicos', 'Serviços Executados'],
    ['responsavel_atividade', 'Responsável Atividade'],
  ];

  function totalDeFotos(rascunho) {
    const anexos = rascunho.anexos || {};
    return (anexos.fotos_intervencao_verificada || []).length + (anexos.fotos_acao_realizada || []).length;
  }

  // Falha nao tem horario programado: nao e exigido (ehFalha = true).
  const CHAVES_SO_FORA_DE_FALHA = ['hora_prog_inicio', 'hora_prog_termino'];

  // 29/10/2026: N° SA obrigatoria so em Preventiva/Preditiva (exigeSa),
  // mesma regra do servidor (rad/validadores.py::_validar_numero_sa).
  // Sem o 3o parametro, mantem o comportamento antigo (exige fora de Falha).
  function camposObrigatoriosFaltando(rascunho, ehFalha, exigeSa = !ehFalha) {
    const faltando = CAMPOS_OBRIGATORIOS_ROTULOS.filter(function ([chave]) {
      if (ehFalha && CHAVES_SO_FORA_DE_FALHA.includes(chave)) return false;
      if (chave === 'numero_sa' && !exigeSa) return false;
      const valor = rascunho[chave];
      if (Array.isArray(valor)) return valor.length === 0;
      return !valor;
    }).map(function ([, rotulo]) {
      return rotulo;
    });
    if (totalDeFotos(rascunho) === 0) {
      faltando.push('Fotos (ao menos 1)');
    }
    return faltando;
  }

  function camposObrigatoriosPreenchidos(rascunho, ehFalha, exigeSa = !ehFalha) {
    return !!(
      rascunho.numero_os &&
      (!exigeSa || rascunho.numero_sa) &&
      rascunho.data_preenchimento &&
      rascunho.data_atividade &&
      rascunho.id_local_inicial &&
      rascunho.id_local_final &&
      rascunho.km_poste_inicial &&
      rascunho.km_poste_final &&
      rascunho.linhas && rascunho.linhas.length > 0 &&
      rascunho.vias && rascunho.vias.length > 0 &&
      rascunho.id_tipo_manutencao &&
      (ehFalha || (rascunho.hora_prog_inicio && rascunho.hora_prog_termino)) &&
      rascunho.hora_real_inicio &&
      rascunho.hora_real_termino &&
      rascunho.servicos && rascunho.servicos.length > 0 &&
      rascunho.responsavel_atividade &&
      totalDeFotos(rascunho) > 0
    );
  }

  return {
    montarCampos,
    gerarMensagemCopiar,
    gerarPdfBlob,
    gerarDocxBlob,
    camposObrigatoriosPreenchidos,
    camposObrigatoriosFaltando,
  };
})();
