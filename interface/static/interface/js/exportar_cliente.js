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

    return [
      ['servicos', 'Atividade', textoServicos],
      ['data_preenchimento', 'Data', formatarDataBr(rascunho.data_preenchimento)],
      ['numero_os', 'OS', ouNA(rascunho.numero_os)],
      ['numero_sa', 'N° SA', ouNA(rascunho.numero_sa)],
      ['numero_falha', 'Falha', ouNA(rascunho.numero_falha)],
      ['local_inicial', 'Local', `${local(rascunho.id_local_inicial)}/${local(rascunho.id_local_final)}`],
      ['linhas', 'Linha', listaOuNA(nomesLinhas)],
      ['vias', 'Via', listaOuNA(nomesVias)],
      ['equipes', 'Equipes Envolvidas', listaOuNA(nomesEquipes)],
      ['km_poste', 'Km/Poste', ouNA(rascunho.km_poste)],
      [
        'hora_prog_inicio', 'Horário programado',
        `${ouNA(rascunho.hora_prog_inicio)} a ${ouNA(rascunho.hora_prog_termino)}`,
      ],
      ['hora_real_inicio', 'Início', ouNA(rascunho.hora_real_inicio)],
      ['hora_real_termino', 'Término', ouNA(rascunho.hora_real_termino)],
      ['servicos', 'Serviços realizados', textoServicos], // duplicado, igual ao backend (EFD 3.13)
      ['materiais_utilizados', 'Equipamentos utilizados', ouNA(rascunho.materiais_utilizados)],
      ['motivo_atraso_inicio', 'Motivo dos atrasos', textoMotivoAtrasos],
      ['colaboradores', 'Responsável', listaOuNA(nomesColaboradores)],
      ['responsavel_atividade', 'Responsável Atividade', ouNA(rascunho.responsavel_atividade)],
      ['operador_ccm', 'Operador CCM', ouNA(rascunho.operador_ccm)],
      ['descricao_tecnica_atividade', 'Descrição Técnica da Atividade', ouNA(rascunho.descricao_tecnica_atividade)],
      ['observacoes_gerais', 'Observação Geral', ouNA(rascunho.observacoes_gerais)],
    ];
  }

  function formatarDataBr(dataIso) {
    if (!dataIso) return NAO_APLICAVEL;
    const [ano, mes, dia] = dataIso.split('-');
    return `${dia}/${mes}/${ano}`;
  }

  function gerarMensagemCopiar(rascunho, catalogos) {
    const campos = montarCampos(rascunho, catalogos);
    const corpo = campos.map(([_chave, rotulo, valor]) => `${rotulo}: ${valor}`).join('\n\n');
    return `RAD - (Relatório de Atividade Diária)\n\n${corpo}`;
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
    ['data_preenchimento', 'Data'],
    ['id_local_inicial', 'Local Inicial'],
    ['id_local_final', 'Local Final'],
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

  function camposObrigatoriosFaltando(rascunho) {
    return CAMPOS_OBRIGATORIOS_ROTULOS.filter(function ([chave]) {
      const valor = rascunho[chave];
      if (Array.isArray(valor)) return valor.length === 0;
      return !valor;
    }).map(function ([, rotulo]) {
      return rotulo;
    });
  }

  function camposObrigatoriosPreenchidos(rascunho) {
    return !!(
      rascunho.numero_os &&
      rascunho.numero_sa &&
      rascunho.data_preenchimento &&
      rascunho.id_local_inicial &&
      rascunho.id_local_final &&
      rascunho.linhas && rascunho.linhas.length > 0 &&
      rascunho.vias && rascunho.vias.length > 0 &&
      rascunho.id_tipo_manutencao &&
      rascunho.hora_prog_inicio &&
      rascunho.hora_prog_termino &&
      rascunho.hora_real_inicio &&
      rascunho.hora_real_termino &&
      rascunho.servicos && rascunho.servicos.length > 0 &&
      rascunho.responsavel_atividade
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
