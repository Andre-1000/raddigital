/*
 * Logica do formulario de preenchimento do RAD.
 */
document.addEventListener('DOMContentLoaded', async function () {
  if (!RadAuth.exigirSessao()) return;

  const sessao = RadAuth.obterSessao();
  document.getElementById('conteudo-protegido').style.display = '';

  const statusRascunho = document.getElementById('status-rascunho');
  const avisoFormulario = document.getElementById('aviso-formulario');

  let rascunho = await RadDB.obterRascunho(sessao.login);
  const jaExistiaRascunho = rascunho !== null;
  if (!rascunho) {
    rascunho = criarRascunhoVazio();
  } else {
    const padrao = criarRascunhoVazio();
    for (const chave in padrao) {
      if (!(chave in rascunho)) rascunho[chave] = padrao[chave];
    }
  }
  if (!rascunho.amv_blocos) {
    // 30/07/2026: migracao defensiva de rascunhos antigos que ainda
    // estejam salvos no formato singular (rascunho.amv) no
    // IndexedDB de algum dispositivo -- converte pra lista, sem
    // perder o que a pessoa ja tinha preenchido.
    if (rascunho.amv && rascunho.amv.id_mch) {
      rascunho.amv_blocos = [rascunho.amv];
    } else {
      rascunho.amv_blocos = [];
    }
  }
  delete rascunho.amv;
  if (!rascunho.anexos) {
    rascunho.anexos = { fotos_intervencao_verificada: [], fotos_acao_realizada: [], pdf: [] };
  }

  let resolverConflitoPendente = null;
  const modalConfirmarExclusao = document.getElementById('modal-confirmar-exclusao');
  const modalConflitoRascunho = document.getElementById('modal-conflito-rascunho');

  document.getElementById('botao-apagar-rascunho').addEventListener('click', function () {
    modalConfirmarExclusao.style.display = 'flex';
  });
  document.getElementById('botao-cancelar-exclusao').addEventListener('click', function () {
    modalConfirmarExclusao.style.display = 'none';
    if (resolverConflitoPendente) {
      modalConflitoRascunho.style.display = 'flex';
    }
  });
  document.getElementById('botao-confirmar-exclusao').addEventListener('click', async function () {
    await RadDB.limparRascunho(sessao.login);
    window.location.reload();
  });

  function rascunhoTemConteudoRelevante(r) {
    return !!(r.numero_os || r.numero_sa || (r.servicos && r.servicos.length > 0));
  }

  async function aguardarResolucaoDeConflito() {
    if (!jaExistiaRascunho || !rascunhoTemConteudoRelevante(rascunho)) return;

    const textoConflito = document.getElementById('texto-conflito-rascunho');
    textoConflito.textContent = rascunho.numero_os
      ? `Você já tem um RAD em preenchimento neste dispositivo (OS ${rascunho.numero_os}).`
      : 'Você já tem um RAD em preenchimento neste dispositivo.';
    modalConflitoRascunho.style.display = 'flex';

    return new Promise(function (resolve) {
      resolverConflitoPendente = resolve;

      document.getElementById('botao-continuar-rascunho').addEventListener('click', function () {
        modalConflitoRascunho.style.display = 'none';
        resolverConflitoPendente = null;
        resolve();
      });

      document.getElementById('botao-apagar-e-comecar-novo').addEventListener('click', function () {
        modalConflitoRascunho.style.display = 'none';
        modalConfirmarExclusao.style.display = 'flex';
      });
    });
  }

  await aguardarResolucaoDeConflito();

  function criarRascunhoVazio() {
    const hoje = new Date();
    const isoData = hoje.toISOString().slice(0, 10);
    return {
      numero_os: null,
      numero_sa: '',
      solicitante_sa: '',
      data_preenchimento: isoData,
      id_local_inicial: '',
      id_local_final: '',
      linhas: [],
      vias: [],
      equipes: ['VP'],
      km_poste: '',
      tipo_veiculo: '',
      operador: '',
      id_tipo_manutencao: null,
      numero_falha: null,
      hora_prog_inicio: '',
      data_hp_inicio: isoData,
      hora_prog_termino: '',
      data_hp_termino: isoData,
      hora_real_inicio: '',
      data_hr_inicio: isoData,
      hora_real_termino: '',
      data_hr_termino: isoData,
      id_motivo_atraso_termino: null,
      desc_motivo_atraso_termino: '',
      servicos: [],
      outros_servico_desc: '',
      desc_foto_1: '',
      desc_foto_2: '',
      desc_foto_3: '',
      desc_foto_4: '',
      terceiros_num_encarregados: '',
      terceiros_num_op_maquina: '',
      terceiros_num_ajudantes: '',
      terceiros_num_motorista: '',
      terceiros_volume: '',
      amv_blocos: [],
      colaboradores: [],
      anexos: {
        fotos_intervencao_verificada: [],
        fotos_acao_realizada: [],
        pdf: [],
      },
      responsavel_atividade: '',
      operador_ccm_abertura_nome: '',
      operador_ccm_abertura_hora: '00:00',
      operador_ccm_entrega_nome: '',
      operador_ccm_entrega_hora: '00:00',
      descricao_tecnica_atividade: '',
      materiais_utilizados: '',
      observacoes_gerais: '',
      sync_id_tentativa: gerarIdTentativa(),
    };
  }

  function gerarIdTentativa() {
    return 'rascunho-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
  }

  async function salvarRascunhoAgora() {
    await RadDB.salvarRascunho(sessao.login, rascunho);
    const agora = new Date();
    statusRascunho.textContent = `Salvo neste dispositivo às ${agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
    atualizarEstadoBotaoExportar();
  }

  function atualizarEstadoBotaoExportar() {
    const habilitado = ExportarCliente.camposObrigatoriosPreenchidos(rascunho);
    const botaoExportar = document.getElementById('botao-exportar');
    const botaoCopiar = document.getElementById('botao-copiar-mensagem');
    [botaoExportar, botaoCopiar].forEach(function (botao) {
      if (!botao) return;
      botao.style.opacity = habilitado ? '1' : '0.6';
    });
  }

  const locais = await RadDB.obterCatalogo('locais');
  const linhas = await RadDB.obterCatalogo('linhas');
  const vias = await RadDB.obterCatalogo('vias');
  const equipes = await RadDB.obterCatalogo('equipes');
  const tiposManutencao = await RadDB.obterCatalogo('tipos_manutencao');

  if (locais.length === 0) {
    avisoFormulario.innerHTML = `
      <div class="aviso aviso--atencao">
        Os catálogos deste dispositivo ainda não foram baixados.
        Conecte-se à internet e volte à tela inicial para atualizá-los antes de preencher um RAD.
      </div>`;
  }

  function rotuloDoLocal(sigla) {
    const local = locais.find((l) => l.sigla === sigla);
    return local ? `${local.sigla} - ${local.nome}` : '';
  }

  function configurarBuscaLocal(inputEl, resultadosEl, chaveRascunho) {
    if (rascunho[chaveRascunho]) {
      inputEl.value = rotuloDoLocal(rascunho[chaveRascunho]);
    }

    function selecionarLocal(local) {
      inputEl.value = `${local.sigla} - ${local.nome}`;
      rascunho[chaveRascunho] = local.sigla;
      resultadosEl.innerHTML = '';
      salvarRascunhoAgora();
    }

    inputEl.addEventListener('input', function () {
      const termo = inputEl.value.trim().toLowerCase();
      resultadosEl.innerHTML = '';
      rascunho[chaveRascunho] = '';

      if (!termo) return;

      const encontrados = locais
        .filter((l) => l.sigla.toLowerCase().includes(termo) || l.nome.toLowerCase().includes(termo))
        .slice(0, 8);

      if (encontrados.length === 0) {
        const aviso = document.createElement('p');
        aviso.className = 'texto-suave';
        aviso.style.fontSize = '0.85rem';
        aviso.textContent = 'Nenhum local encontrado.';
        resultadosEl.appendChild(aviso);
        return;
      }

      encontrados.forEach(function (local) {
        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'botao botao--secundaria';
        botao.style.textAlign = 'left';
        botao.style.justifyContent = 'flex-start';
        botao.textContent = `${local.sigla} — ${local.nome}`;
        botao.addEventListener('click', function () {
          selecionarLocal(local);
        });
        resultadosEl.appendChild(botao);
      });
    });

    inputEl.addEventListener('blur', function () {
      setTimeout(function () {
        resultadosEl.innerHTML = '';
      }, 150);
    });
  }

  configurarBuscaLocal(
    document.getElementById('campo-local-inicial'),
    document.getElementById('resultados-local-inicial'),
    'id_local_inicial'
  );
  configurarBuscaLocal(
    document.getElementById('campo-local-final'),
    document.getElementById('resultados-local-final'),
    'id_local_final'
  );

  function renderizarChips(containerEl, itens, valoresSelecionados, aoMudar, fixos = []) {
    containerEl.innerHTML = '';
    itens.forEach(function (item) {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.textContent = item.rotulo;
      const selecionado = valoresSelecionados.includes(item.valor);
      chip.setAttribute('aria-pressed', selecionado ? 'true' : 'false');

      const ehFixo = fixos.includes(item.valor);
      if (ehFixo) chip.disabled = true;

      chip.addEventListener('click', function () {
        if (ehFixo) return;
        const indice = valoresSelecionados.indexOf(item.valor);
        if (indice === -1) {
          valoresSelecionados.push(item.valor);
        } else {
          valoresSelecionados.splice(indice, 1);
        }
        chip.setAttribute('aria-pressed', valoresSelecionados.includes(item.valor) ? 'true' : 'false');
        aoMudar();
      });

      containerEl.appendChild(chip);
    });
  }

  renderizarChips(
    document.getElementById('chips-linhas'),
    linhas.map((l) => ({ valor: l.codigo, rotulo: `${l.codigo} - ${l.nome}` })),
    rascunho.linhas,
    salvarRascunhoAgora
  );

  renderizarChips(
    document.getElementById('chips-vias'),
    vias.map((v) => ({ valor: v.id, rotulo: v.nome })),
    rascunho.vias,
    salvarRascunhoAgora
  );

  renderizarChips(
    document.getElementById('chips-equipes'),
    equipes.map((e) => ({ valor: e.codigo, rotulo: e.nome })),
    rascunho.equipes,
    salvarRascunhoAgora,
    ['VP']
  );

  const campoKmPoste = document.getElementById('campo-km-poste');
  campoKmPoste.value = rascunho.km_poste || '';

  function aplicarMascaraKmPoste(valorDigitado) {
    const digitos = valorDigitado.replace(/\D/g, '').slice(0, 8);
    let resultado = digitos;
    if (digitos.length > 2) resultado = digitos.slice(0, 2) + '/' + digitos.slice(2);
    if (digitos.length > 4) resultado = resultado.slice(0, 5) + ' - ' + digitos.slice(4);
    if (digitos.length > 6) resultado = resultado.slice(0, 10) + '/' + digitos.slice(6);
    return resultado;
  }

  campoKmPoste.addEventListener('input', function () {
    const somenteDigitos = /^\d+$/.test(campoKmPoste.value.replace(/[/\s-]/g, ''));
    if (somenteDigitos) {
      campoKmPoste.value = aplicarMascaraKmPoste(campoKmPoste.value);
    }
    rascunho.km_poste = campoKmPoste.value;
    salvarRascunhoAgora();
  });

  const campoTipoManutencao = document.getElementById('campo-tipo-manutencao');
  tiposManutencao.forEach(function (tipo) {
    const opcao = document.createElement('option');
    opcao.value = tipo.id;
    opcao.textContent = tipo.nome;
    campoTipoManutencao.appendChild(opcao);
  });
  if (rascunho.id_tipo_manutencao) {
    campoTipoManutencao.value = rascunho.id_tipo_manutencao;
  }

  const campoGrupoNumeroFalha = document.getElementById('campo-grupo-numero-falha');
  const campoNumeroFalha = document.getElementById('campo-numero-falha');
  campoNumeroFalha.value = rascunho.numero_falha || '';

  function nomeDoTipoSelecionado() {
    const tipo = tiposManutencao.find((t) => String(t.id) === String(campoTipoManutencao.value));
    return tipo ? tipo.nome : '';
  }

  function atualizarVisibilidadeNumeroFalha() {
    const ehFalha = nomeDoTipoSelecionado() === 'Falha';
    campoGrupoNumeroFalha.style.display = ehFalha ? '' : 'none';
    if (!ehFalha) {
      campoNumeroFalha.value = '';
      rascunho.numero_falha = null;
    }
  }
  atualizarVisibilidadeNumeroFalha();

  // 30/07/2026: os campos de comentario de foto (desc_foto_1..4)
  // deixaram de ter caixas fixas aqui -- agora moram no bloco Anexos,
  // acionados por botao (ver atualizarComentariosFotos, mais abaixo,
  // e a secao "Comentarios das fotos"). ehVpm001Selecionado()
  // continua aqui porque tambem e usada por atualizarVisibilidadeNumeroFalha
  // (nao, so por comentarios -- mas fica perto do resto da logica de
  // Tipo de Manutencao por clareza).
  function ehVpm001Selecionado() {
    return nomeDoTipoSelecionado() === 'VPM001';
  }

  campoTipoManutencao.addEventListener('change', function () {
    rascunho.id_tipo_manutencao = campoTipoManutencao.value ? Number(campoTipoManutencao.value) : null;
    atualizarVisibilidadeNumeroFalha();
    atualizarComentariosFotos();
    salvarRascunhoAgora();
  });

  campoNumeroFalha.addEventListener('input', function () {
    rascunho.numero_falha = campoNumeroFalha.value ? Number(campoNumeroFalha.value) : null;
    salvarRascunhoAgora();
  });

  const modalAjuda = document.getElementById('modal-ajuda-tipo-manutencao');
  document.getElementById('botao-ajuda-tipo-manutencao').addEventListener('click', function () {
    modalAjuda.style.display = 'flex';
  });
  document.getElementById('botao-fechar-ajuda').addEventListener('click', function () {
    modalAjuda.style.display = 'none';
  });
  modalAjuda.addEventListener('click', function (evento) {
    if (evento.target === modalAjuda) modalAjuda.style.display = 'none';
  });

  const campoNumeroOs = document.getElementById('campo-numero-os');
  const campoNumeroSa = document.getElementById('campo-numero-sa');
  const campoSolicitanteSa = document.getElementById('campo-solicitante-sa');
  const campoData = document.getElementById('campo-data');

  campoNumeroOs.value = rascunho.numero_os || '';
  campoNumeroSa.value = rascunho.numero_sa || '';
  campoSolicitanteSa.value = rascunho.solicitante_sa || '';
  campoData.value = rascunho.data_preenchimento || '';

  campoNumeroOs.addEventListener('input', function () {
    rascunho.numero_os = campoNumeroOs.value ? Number(campoNumeroOs.value) : null;
    salvarRascunhoAgora();
  });
  campoNumeroSa.addEventListener('input', function () {
    campoNumeroSa.value = campoNumeroSa.value.replace(/\D/g, '').slice(0, 10);
    rascunho.numero_sa = campoNumeroSa.value;
    salvarRascunhoAgora();
  });
  campoSolicitanteSa.addEventListener('input', function () {
    rascunho.solicitante_sa = campoSolicitanteSa.value;
    salvarRascunhoAgora();
  });
  campoData.addEventListener('change', function () {
    rascunho.data_preenchimento = campoData.value;
    salvarRascunhoAgora();
  });

  await salvarRascunhoAgora();

  const motivosAtraso = await RadDB.obterCatalogo('motivos_atraso');

  const campoHpInicio = document.getElementById('campo-hp-inicio');
  const campoDataHpInicio = document.getElementById('campo-data-hp-inicio');
  const campoHpTermino = document.getElementById('campo-hp-termino');
  const campoDataHpTermino = document.getElementById('campo-data-hp-termino');
  const campoHrInicio = document.getElementById('campo-hr-inicio');
  const campoDataHrInicio = document.getElementById('campo-data-hr-inicio');
  const campoHrTermino = document.getElementById('campo-hr-termino');
  const campoDataHrTermino = document.getElementById('campo-data-hr-termino');

  const valorDuracaoProgramada = document.getElementById('valor-duracao-programada');
  const valorDuracaoReal = document.getElementById('valor-duracao-real');

  const grupoAtrasoTermino = document.getElementById('campo-grupo-atraso-termino');
  const selectMotivoTermino = document.getElementById('campo-motivo-atraso-termino');
  const grupoDescTermino = document.getElementById('campo-grupo-desc-atraso-termino');
  const campoDescTermino = document.getElementById('campo-desc-atraso-termino');

  const hojeIso = new Date().toISOString().slice(0, 10);
  campoDataHpInicio.max = hojeIso;
  campoDataHrInicio.max = hojeIso;

  const opcaoVaziaMotivoTermino = document.createElement('option');
  opcaoVaziaMotivoTermino.value = '';
  opcaoVaziaMotivoTermino.textContent = 'Selecione…';
  selectMotivoTermino.appendChild(opcaoVaziaMotivoTermino);
  motivosAtraso.forEach(function (motivo) {
    const opcao = document.createElement('option');
    opcao.value = motivo.id;
    opcao.textContent = motivo.nome;
    selectMotivoTermino.appendChild(opcao);
  });

  function nomeDoMotivo(lista, id) {
    const motivo = lista.find((m) => String(m.id) === String(id));
    return motivo ? motivo.nome : '';
  }

  let dataHpTerminoEditadaManualmente = !!rascunho._dataHpTerminoEditada;
  let dataHrTerminoEditadaManualmente = !!rascunho._dataHrTerminoEditada;

  function preencherCamposIniciais() {
    campoHpInicio.value = rascunho.hora_prog_inicio || '';
    campoDataHpInicio.value = rascunho.data_hp_inicio || rascunho.data_preenchimento;
    campoHpTermino.value = rascunho.hora_prog_termino || '';
    campoDataHpTermino.value = rascunho.data_hp_termino || rascunho.data_preenchimento;
    campoHrInicio.value = rascunho.hora_real_inicio || '';
    campoDataHrInicio.value = rascunho.data_hr_inicio || rascunho.data_preenchimento;
    campoHrTermino.value = rascunho.hora_real_termino || '';
    campoDataHrTermino.value = rascunho.data_hr_termino || rascunho.data_preenchimento;
  }
  preencherCamposIniciais();

  function tipoManutencaoEhFalha() {
    return nomeDoTipoSelecionado() === 'Falha';
  }

  function recalcularHorarios() {
    if (rascunho.hora_prog_inicio && rascunho.hora_prog_termino && !dataHpTerminoEditadaManualmente) {
      const novaData = RegrasHorario.ajustarDataPorViradaDeMeiaNoite(
        campoDataHpInicio.value, rascunho.hora_prog_inicio, rascunho.hora_prog_termino
      );
      campoDataHpTermino.value = novaData;
      rascunho.data_hp_termino = novaData;
    }
    if (rascunho.hora_real_inicio && rascunho.hora_real_termino && !dataHrTerminoEditadaManualmente) {
      const novaData = RegrasHorario.ajustarDataPorViradaDeMeiaNoite(
        campoDataHrInicio.value, rascunho.hora_real_inicio, rascunho.hora_real_termino
      );
      campoDataHrTermino.value = novaData;
      rascunho.data_hr_termino = novaData;
    }

    let dtProgInicio = null, dtProgTermino = null, dtRealInicio = null, dtRealTermino = null;

    if (rascunho.hora_prog_inicio && campoDataHpInicio.value) {
      dtProgInicio = RegrasHorario.montarDataHora(campoDataHpInicio.value, rascunho.hora_prog_inicio);
    }
    if (rascunho.hora_prog_termino && campoDataHpTermino.value) {
      dtProgTermino = RegrasHorario.montarDataHora(campoDataHpTermino.value, rascunho.hora_prog_termino);
    }
    if (rascunho.hora_real_inicio && campoDataHrInicio.value) {
      dtRealInicio = RegrasHorario.montarDataHora(campoDataHrInicio.value, rascunho.hora_real_inicio);
    }
    if (rascunho.hora_real_termino && campoDataHrTermino.value) {
      dtRealTermino = RegrasHorario.montarDataHora(campoDataHrTermino.value, rascunho.hora_real_termino);
    }

    if (dtProgInicio && dtProgTermino) {
      valorDuracaoProgramada.textContent = RegrasHorario.formatarDuracao(
        RegrasHorario.calcularDuracaoMinutos(dtProgInicio, dtProgTermino)
      );
    } else {
      valorDuracaoProgramada.textContent = '--';
    }
    if (dtRealInicio && dtRealTermino) {
      valorDuracaoReal.textContent = RegrasHorario.formatarDuracao(
        RegrasHorario.calcularDuracaoMinutos(dtRealInicio, dtRealTermino)
      );
    } else {
      valorDuracaoReal.textContent = '--';
    }

    const ocultarAtrasos = tipoManutencaoEhFalha();
    let atrasoTermino = false;

    if (!ocultarAtrasos && dtProgTermino && dtRealTermino) {
      atrasoTermino = RegrasHorario.calcularAtrasoTermino(dtProgTermino, dtRealTermino);
    }

    grupoAtrasoTermino.style.display = atrasoTermino ? '' : 'none';

    if (!atrasoTermino) {
      rascunho.id_motivo_atraso_termino = null;
      rascunho.desc_motivo_atraso_termino = '';
      selectMotivoTermino.value = '';
      campoDescTermino.value = '';
      grupoDescTermino.style.display = 'none';
    }
  }
  recalcularHorarios();

  function aoMudarHora(campoInputEl, chaveRascunho) {
    campoInputEl.addEventListener('change', function () {
      rascunho[chaveRascunho] = campoInputEl.value;
      recalcularHorarios();
      salvarRascunhoAgora();
    });
  }
  aoMudarHora(campoHpInicio, 'hora_prog_inicio');
  aoMudarHora(campoHpTermino, 'hora_prog_termino');
  aoMudarHora(campoHrInicio, 'hora_real_inicio');
  aoMudarHora(campoHrTermino, 'hora_real_termino');

  campoDataHpInicio.addEventListener('change', function () {
    rascunho.data_hp_inicio = campoDataHpInicio.value;
    recalcularHorarios();
    salvarRascunhoAgora();
  });
  campoDataHrInicio.addEventListener('change', function () {
    rascunho.data_hr_inicio = campoDataHrInicio.value;
    recalcularHorarios();
    salvarRascunhoAgora();
  });
  campoDataHpTermino.addEventListener('change', function () {
    dataHpTerminoEditadaManualmente = true;
    rascunho._dataHpTerminoEditada = true;
    rascunho.data_hp_termino = campoDataHpTermino.value;
    recalcularHorarios();
    salvarRascunhoAgora();
  });
  campoDataHrTermino.addEventListener('change', function () {
    dataHrTerminoEditadaManualmente = true;
    rascunho._dataHrTerminoEditada = true;
    rascunho.data_hr_termino = campoDataHrTermino.value;
    recalcularHorarios();
    salvarRascunhoAgora();
  });

  selectMotivoTermino.addEventListener('change', function () {
    rascunho.id_motivo_atraso_termino = selectMotivoTermino.value ? Number(selectMotivoTermino.value) : null;
    const ehOutros = nomeDoMotivo(motivosAtraso, selectMotivoTermino.value) === 'Outros';
    grupoDescTermino.style.display = ehOutros ? '' : 'none';
    if (!ehOutros) {
      rascunho.desc_motivo_atraso_termino = '';
      campoDescTermino.value = '';
    }
    salvarRascunhoAgora();
  });
  campoDescTermino.addEventListener('input', function () {
    rascunho.desc_motivo_atraso_termino = campoDescTermino.value;
    salvarRascunhoAgora();
  });

  campoTipoManutencao.addEventListener('change', recalcularHorarios);

  const servicosCarregados = await RadDB.obterCatalogo('servicos');
  const mchs = await RadDB.obterCatalogo('mch');
  const tiposDefeitoAmv = await RadDB.obterCatalogo('tipos_defeito_amv');
  const acoesAmv = await RadDB.obterCatalogo('acoes_amv');
  const limitesFotos = await RadDB.obterCatalogo('limites_fotos');

  function ordenarComOutrosPorUltimo(lista) {
    const semOutros = lista.filter((item) => item.nome !== 'Outros');
    const outros = lista.filter((item) => item.nome === 'Outros');
    semOutros.sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
    return [...semOutros, ...outros];
  }
  const servicos = ordenarComOutrosPorUltimo(servicosCarregados);

  const listaServicosEl = document.getElementById('lista-servicos');
  const grupoOutrosServico = document.getElementById('campo-grupo-outros-servico');
  const campoOutrosServicoDesc = document.getElementById('campo-outros-servico-desc');
  const blocoAmv = document.getElementById('bloco-amv');

  function renderizarListaCheckbox(containerEl, itens, valoresSelecionados, aoMudar) {
    containerEl.innerHTML = '';
    itens.forEach(function (item) {
      const linha = document.createElement('label');

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.style.marginTop = '0.3rem';
      checkbox.style.minWidth = '20px';
      checkbox.style.minHeight = '20px';
      checkbox.checked = valoresSelecionados.includes(item.valor);
      checkbox.addEventListener('change', function () {
        const indice = valoresSelecionados.indexOf(item.valor);
        if (checkbox.checked && indice === -1) {
          valoresSelecionados.push(item.valor);
        } else if (!checkbox.checked && indice !== -1) {
          valoresSelecionados.splice(indice, 1);
        }
        aoMudar(item, checkbox.checked);
      });

      const textoWrapper = document.createElement('span');
      textoWrapper.textContent = item.rotulo;
      linha.appendChild(checkbox);
      linha.appendChild(textoWrapper);
      containerEl.appendChild(linha);
    });
  }

  // 30/07/2026: Servicos Executados agora e organizado em blocos
  // expansiveis (Geral, Infra, Corretiva, Mecanizada) -- cada grupo
  // comeca fechado e o usuario clica pra expandir e ver os servicos
  // daquele grupo. Usa o elemento nativo <details>/<summary> do HTML:
  // ganha comportamento de clique/teclado de graca, sem precisar
  // escrever logica de abrir/fechar na mao. "Outros" fica de fora dos
  // grupos, sempre visivel no final (e um catch-all, nao uma
  // categoria). Um grupo que ja tem servico selecionado comeca aberto
  // (RG: nunca esconder uma selecao existente do usuario sem ele
  // pedir), e o cabecalho mostra quantos estao marcados mesmo fechado.
  const ROTULOS_GRUPO_SERVICO = {
    geral: 'Geral',
    infra: 'Infra',
    corretiva: 'Corretiva',
    mecanizada: 'Mecanizada',
    amv: 'AMV',
  };
  const ORDEM_GRUPOS_SERVICO = ['geral', 'infra', 'corretiva', 'mecanizada', 'amv'];

  function criarLinhaCheckboxServico(servico, valoresSelecionados, aoMudar) {
    const linha = document.createElement('label');

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.style.marginTop = '0.3rem';
    checkbox.style.minWidth = '20px';
    checkbox.style.minHeight = '20px';
    checkbox.checked = valoresSelecionados.includes(servico.id);
    checkbox.addEventListener('change', function () {
      const indice = valoresSelecionados.indexOf(servico.id);
      if (checkbox.checked && indice === -1) {
        valoresSelecionados.push(servico.id);
      } else if (!checkbox.checked && indice !== -1) {
        valoresSelecionados.splice(indice, 1);
      }
      aoMudar(servico, checkbox.checked);
    });

    const textoWrapper = document.createElement('span');
    textoWrapper.textContent = servico.nome;
    linha.appendChild(checkbox);
    linha.appendChild(textoWrapper);
    return linha;
  }

  function renderizarServicosAgrupados(containerEl, servicosOrdenados, valoresSelecionados, aoMudar) {
    containerEl.innerHTML = '';

    const outros = servicosOrdenados.filter((s) => s.nome === 'Outros');

    ORDEM_GRUPOS_SERVICO.forEach(function (chaveGrupo) {
      const itensDoGrupo = servicosOrdenados.filter(
        (s) => (s.area || 'geral') === chaveGrupo && s.nome !== 'Outros'
      );
      if (itensDoGrupo.length === 0) return; // grupo sem nenhum servico ativo: nem aparece

      const detalhes = document.createElement('details');
      detalhes.className = 'grupo-servicos';

      const resumo = document.createElement('summary');
      resumo.className = 'grupo-servicos__cabecalho';
      detalhes.appendChild(resumo);

      const corpo = document.createElement('div');
      corpo.className = 'grade-checkboxes grupo-servicos__corpo';
      detalhes.appendChild(corpo);

      function atualizarRotuloResumo() {
        const quantidadeSelecionada = itensDoGrupo.filter((s) => valoresSelecionados.includes(s.id)).length;
        resumo.textContent = quantidadeSelecionada > 0
          ? `${ROTULOS_GRUPO_SERVICO[chaveGrupo]} (${quantidadeSelecionada} selecionado${quantidadeSelecionada > 1 ? 's' : ''})`
          : ROTULOS_GRUPO_SERVICO[chaveGrupo];
      }
      atualizarRotuloResumo();

      itensDoGrupo.forEach(function (servico) {
        const linha = criarLinhaCheckboxServico(servico, valoresSelecionados, function (item, marcado) {
          atualizarRotuloResumo();
          aoMudar(item, marcado);
        });
        corpo.appendChild(linha);
      });

      // Comeca aberto se ja tem algo marcado -- nunca esconder uma
      // selecao existente sem o usuario pedir.
      detalhes.open = itensDoGrupo.some((s) => valoresSelecionados.includes(s.id));

      containerEl.appendChild(detalhes);
    });

    if (outros.length > 0) {
      const corpoOutros = document.createElement('div');
      corpoOutros.className = 'grade-checkboxes';
      containerEl.appendChild(corpoOutros);
      outros.forEach(function (servico) {
        corpoOutros.appendChild(criarLinhaCheckboxServico(servico, valoresSelecionados, aoMudar));
      });
    }
  }

  const modalSobreServicos = document.getElementById('modal-sobre-servicos');
  const selectServicoExplicacao = document.getElementById('select-servico-explicacao');
  const textoExplicacaoServico = document.getElementById('texto-explicacao-servico');

  servicos.forEach(function (servico) {
    const opcao = document.createElement('option');
    opcao.value = servico.id;
    opcao.textContent = servico.nome;
    selectServicoExplicacao.appendChild(opcao);
  });

  selectServicoExplicacao.addEventListener('change', function () {
    const servico = servicos.find((s) => String(s.id) === selectServicoExplicacao.value);
    textoExplicacaoServico.textContent = servico ? (servico.descricao || 'Sem descrição cadastrada.') : '';
  });

  document.getElementById('botao-sobre-servicos').addEventListener('click', function () {
    selectServicoExplicacao.value = '';
    textoExplicacaoServico.textContent = '';
    modalSobreServicos.style.display = 'flex';
  });
  document.getElementById('botao-fechar-sobre-servicos').addEventListener('click', function () {
    modalSobreServicos.style.display = 'none';
  });

  function servicoRequerAmvSelecionado() {
    return servicos.some((s) => s.requer_amv && rascunho.servicos.includes(s.id));
  }
  function servicoOutrosSelecionado() {
    return servicos.some((s) => s.requer_descricao && rascunho.servicos.includes(s.id));
  }
  function servicoRequerTerceirosSelecionado() {
    return servicos.some((s) => s.requer_terceiros && rascunho.servicos.includes(s.id));
  }
  function algumServicoSelecionadoTem(flag) {
    return servicos.some((s) => s[flag] && rascunho.servicos.includes(s.id));
  }

  // 30/07/2026: limite de fotos configuravel (Configuracoes -> Limites
  // de Fotos), e varia conforme a area do(s) servico(s) selecionado(s)
  // -- Infra permite mais fotos que o padrao (Geral e demais areas).
  // limitesFotos vem do mesmo pacote offline dos demais catalogos
  // (RadDB.obterCatalogo), entao funciona sem conexao tambem.
  function servicoInfraSelecionado() {
    return servicos.some((s) => s.area === 'infra' && rascunho.servicos.includes(s.id));
  }

  function limiteFotoAtual(categoria) {
    const area = servicoInfraSelecionado() ? 'infra' : 'padrao';
    const item = limitesFotos.find((l) => l.categoria === categoria && l.area === area);
    return item ? item.limite : ValidadoresArquivos.LIMITE_FOTOS_POR_CATEGORIA;
  }

  // Declarados aqui (antes de atualizarVisibilidadeServicos, que ja e
  // chamada mais abaixo) para que a primeira chamada nao quebre por
  // referenciar algo ainda nao declarado. atualizadoresLimiteFoto
  // comeca vazio e e populado depois, quando os grupos de anexo forem
  // configurados (configurarGrupoAnexo) -- chamar .forEach nele antes
  // disso e inofensivo (so nao faz nada ainda).
  const atualizadoresLimiteFoto = [];
  const rotuloLimiteIntervencao = document.getElementById('rotulo-limite-intervencao');
  const rotuloLimiteAcao = document.getElementById('rotulo-limite-acao');

  function atualizarRotulosLimiteFoto() {
    if (rotuloLimiteIntervencao) {
      rotuloLimiteIntervencao.textContent = `(até ${limiteFotoAtual('intervencao_verificada')})`;
    }
    if (rotuloLimiteAcao) {
      rotuloLimiteAcao.textContent = `(até ${limiteFotoAtual('acao_realizada')})`;
    }
  }

  function atualizarLimitesDeFotoNaTela() {
    atualizarRotulosLimiteFoto();
    atualizadoresLimiteFoto.forEach(function (atualizar) {
      atualizar();
    });
  }

  // 30/07/2026: Bloco AMV agora suporta varios blocos (um por MCH
  // verificada nesse RAD, ate MAXIMO_BLOCOS_AMV). Nao ha mais campos
  // fixos no HTML (campo-mch, lista-tipos-defeito etc.) -- cada bloco
  // e criado inteiramente por JS dentro de #container-blocos-amv, com
  // seus proprios elementos, independentes dos outros blocos.
  const MAXIMO_BLOCOS_AMV = 16;
  const containerBlocosAmv = document.getElementById('container-blocos-amv');
  const botaoAdicionarMch = document.getElementById('botao-adicionar-mch');
  const contadorBlocosAmv = document.getElementById('contador-blocos-amv');

  function criarBlocoAmvVazio() {
    return { id_mch: null, tipos_defeito: [], acoes: [], desc_outros_tipo_defeito: '', desc_outros_acao: '' };
  }

  function montarDetalhesMchTexto(idMch) {
    const mch = mchs.find((m) => m.id === idMch);
    return {
      modelo: mch ? mch.modelo || '—' : '—',
      via: mch ? mch.via || '—' : '—',
      ur: mch ? mch.ur || '—' : '—',
      local: mch ? mch.local_amv || '—' : '—',
      linha: mch ? mch.linha || '—' : '—',
    };
  }

  function renderizarBlocoAmvIndividual(bloco, indice) {
    const cartao = document.createElement('div');
    cartao.className = 'cartao bloco-amv';

    const cabecalho = document.createElement('div');
    cabecalho.className = 'bloco-amv__cabecalho';
    const titulo = document.createElement('p');
    titulo.className = 'bloco-amv__titulo';
    titulo.textContent = `Bloco AMV — ${indice + 1} de ${rascunho.amv_blocos.length}`;
    cabecalho.appendChild(titulo);

    if (indice > 0) {
      // O primeiro bloco nunca e removivel -- precisa de ao menos 1
      // enquanto "Manutencao em AMV" estiver selecionado (VLD-020).
      const botaoRemover = document.createElement('button');
      botaoRemover.type = 'button';
      botaoRemover.className = 'botao botao--perigo';
      botaoRemover.style.width = 'auto';
      botaoRemover.style.minHeight = '32px';
      botaoRemover.style.padding = '0 0.8rem';
      botaoRemover.style.fontSize = '0.8rem';
      botaoRemover.textContent = 'Remover';
      botaoRemover.addEventListener('click', function () {
        rascunho.amv_blocos.splice(indice, 1);
        renderizarBlocosAmv();
        salvarRascunhoAgora();
      });
      cabecalho.appendChild(botaoRemover);
    }
    cartao.appendChild(cabecalho);

    // --- Identificacao MCH ---
    const campoMchGrupo = document.createElement('div');
    campoMchGrupo.className = 'campo';
    const idListaMch = `lista-mch-${indice}`;
    campoMchGrupo.innerHTML = `<label>Identificação MCH</label>`;
    const inputMch = document.createElement('input');
    inputMch.type = 'text';
    inputMch.setAttribute('list', idListaMch);
    inputMch.autocomplete = 'off';
    inputMch.placeholder = 'Buscar MCH…';
    const mchAtual = mchs.find((m) => m.id === bloco.id_mch);
    inputMch.value = mchAtual ? mchAtual.identificacao : '';
    campoMchGrupo.appendChild(inputMch);

    const datalist = document.createElement('datalist');
    datalist.id = idListaMch;
    mchs.forEach(function (mch) {
      const opcao = document.createElement('option');
      opcao.value = mch.identificacao;
      datalist.appendChild(opcao);
    });
    campoMchGrupo.appendChild(datalist);

    const detalhesMchEl = document.createElement('div');
    detalhesMchEl.className = 'bloco-amv__detalhes-mch';

    function atualizarDetalhesMch() {
      if (!bloco.id_mch) {
        detalhesMchEl.style.display = 'none';
        return;
      }
      const detalhes = montarDetalhesMchTexto(bloco.id_mch);
      detalhesMchEl.innerHTML = `
        <div><span class="texto-suave" style="font-size:0.8rem;">Modelo</span><br><strong>${detalhes.modelo}</strong></div>
        <div><span class="texto-suave" style="font-size:0.8rem;">Via</span><br><strong>${detalhes.via}</strong></div>
        <div><span class="texto-suave" style="font-size:0.8rem;">UR</span><br><strong>${detalhes.ur}</strong></div>
        <div><span class="texto-suave" style="font-size:0.8rem;">Local</span><br><strong>${detalhes.local}</strong></div>
        <div><span class="texto-suave" style="font-size:0.8rem;">Linha</span><br><strong>${detalhes.linha}</strong></div>
      `;
      detalhesMchEl.style.display = 'flex';
    }
    atualizarDetalhesMch();
    campoMchGrupo.appendChild(detalhesMchEl);

    inputMch.addEventListener('change', function () {
      const mchEncontrada = mchs.find((m) => m.identificacao === inputMch.value.trim());
      bloco.id_mch = mchEncontrada ? mchEncontrada.id : null;
      atualizarDetalhesMch();
      salvarRascunhoAgora();
    });
    cartao.appendChild(campoMchGrupo);

    // --- Tipo de Defeito ---
    const grupoDefeito = document.createElement('div');
    grupoDefeito.className = 'campo';
    grupoDefeito.innerHTML = '<label>Tipo de Defeito</label>';
    const listaDefeitoEl = document.createElement('div');
    listaDefeitoEl.className = 'pilha';
    grupoDefeito.appendChild(listaDefeitoEl);

    const grupoOutrosDefeito = document.createElement('div');
    grupoOutrosDefeito.style.marginTop = '0.6rem';
    grupoOutrosDefeito.innerHTML = '<label>Descreva o tipo de defeito</label>';
    const campoOutrosDefeito = document.createElement('textarea');
    campoOutrosDefeito.maxLength = 500;
    campoOutrosDefeito.value = bloco.desc_outros_tipo_defeito || '';
    campoOutrosDefeito.addEventListener('input', function () {
      bloco.desc_outros_tipo_defeito = campoOutrosDefeito.value;
      salvarRascunhoAgora();
    });
    grupoOutrosDefeito.appendChild(campoOutrosDefeito);
    grupoDefeito.appendChild(grupoOutrosDefeito);

    function atualizarVisibilidadeOutrosDefeito() {
      const outrosSelecionado = tiposDefeitoAmv.some(
        (t) => t.requer_descricao && bloco.tipos_defeito.includes(t.id)
      );
      grupoOutrosDefeito.style.display = outrosSelecionado ? '' : 'none';
      if (!outrosSelecionado) {
        bloco.desc_outros_tipo_defeito = '';
        campoOutrosDefeito.value = '';
      }
    }
    renderizarListaCheckbox(
      listaDefeitoEl,
      tiposDefeitoAmv.map((t) => ({ valor: t.id, rotulo: t.nome })),
      bloco.tipos_defeito,
      function () {
        atualizarVisibilidadeOutrosDefeito();
        salvarRascunhoAgora();
      }
    );
    atualizarVisibilidadeOutrosDefeito();
    cartao.appendChild(grupoDefeito);

    // --- Acoes ---
    const grupoAcoes = document.createElement('div');
    grupoAcoes.className = 'campo';
    grupoAcoes.innerHTML = '<label>Ações</label>';
    const listaAcoesEl = document.createElement('div');
    listaAcoesEl.className = 'pilha';
    grupoAcoes.appendChild(listaAcoesEl);

    const grupoOutrosAcao = document.createElement('div');
    grupoOutrosAcao.style.marginTop = '0.6rem';
    grupoOutrosAcao.innerHTML = '<label>Descreva a ação</label>';
    const campoOutrosAcao = document.createElement('textarea');
    campoOutrosAcao.maxLength = 500;
    campoOutrosAcao.value = bloco.desc_outros_acao || '';
    campoOutrosAcao.addEventListener('input', function () {
      bloco.desc_outros_acao = campoOutrosAcao.value;
      salvarRascunhoAgora();
    });
    grupoOutrosAcao.appendChild(campoOutrosAcao);
    grupoAcoes.appendChild(grupoOutrosAcao);

    function atualizarVisibilidadeOutrosAcao() {
      const outrosSelecionada = acoesAmv.some(
        (a) => a.requer_descricao && bloco.acoes.includes(a.id)
      );
      grupoOutrosAcao.style.display = outrosSelecionada ? '' : 'none';
      if (!outrosSelecionada) {
        bloco.desc_outros_acao = '';
        campoOutrosAcao.value = '';
      }
    }
    renderizarListaCheckbox(
      listaAcoesEl,
      acoesAmv.map((a) => ({ valor: a.id, rotulo: a.nome })),
      bloco.acoes,
      function () {
        atualizarVisibilidadeOutrosAcao();
        salvarRascunhoAgora();
      }
    );
    atualizarVisibilidadeOutrosAcao();
    cartao.appendChild(grupoAcoes);

    return cartao;
  }

  function renderizarBlocosAmv() {
    containerBlocosAmv.innerHTML = '';
    rascunho.amv_blocos.forEach(function (bloco, indice) {
      containerBlocosAmv.appendChild(renderizarBlocoAmvIndividual(bloco, indice));
    });
    contadorBlocosAmv.textContent = `${rascunho.amv_blocos.length} de ${MAXIMO_BLOCOS_AMV} blocos usados`;
    botaoAdicionarMch.style.display = rascunho.amv_blocos.length >= MAXIMO_BLOCOS_AMV ? 'none' : '';
  }

  botaoAdicionarMch.addEventListener('click', function () {
    if (rascunho.amv_blocos.length >= MAXIMO_BLOCOS_AMV) return;
    rascunho.amv_blocos.push(criarBlocoAmvVazio());
    renderizarBlocosAmv();
    salvarRascunhoAgora();
  });

  const blocoTerceiros = document.getElementById('bloco-terceiros');
  const campoGrupoTerceirosOpMaquina = document.getElementById('campo-grupo-terceiros-op-maquina');
  const campoGrupoTerceirosVolume = document.getElementById('campo-grupo-terceiros-volume');

  function limparCampoTerceiros(elementoId, chaveRascunho) {
    document.getElementById(elementoId).value = '';
    rascunho[chaveRascunho] = '';
  }

  function atualizarVisibilidadeServicos() {
    grupoOutrosServico.style.display = servicoOutrosSelecionado() ? '' : 'none';
    if (!servicoOutrosSelecionado()) {
      rascunho.outros_servico_desc = '';
      campoOutrosServicoDesc.value = '';
    }

    if (servicoRequerAmvSelecionado()) {
      blocoAmv.style.display = '';
      if (rascunho.amv_blocos.length === 0) {
        rascunho.amv_blocos.push(criarBlocoAmvVazio());
      }
      renderizarBlocosAmv();
    } else {
      blocoAmv.style.display = 'none';
      rascunho.amv_blocos.length = 0;
      containerBlocosAmv.innerHTML = '';
    }

    if (servicoRequerTerceirosSelecionado()) {
      blocoTerceiros.style.display = '';
      campoGrupoTerceirosOpMaquina.style.display = algumServicoSelecionadoTem('terceiros_tem_op_maquina') ? '' : 'none';
      campoGrupoTerceirosVolume.style.display = algumServicoSelecionadoTem('terceiros_tem_volume') ? '' : 'none';
      if (campoGrupoTerceirosOpMaquina.style.display === 'none') {
        limparCampoTerceiros('campo-terceiros-op-maquina', 'terceiros_num_op_maquina');
      }
      if (campoGrupoTerceirosVolume.style.display === 'none') {
        limparCampoTerceiros('campo-terceiros-volume', 'terceiros_volume');
      }
    } else {
      blocoTerceiros.style.display = 'none';
      limparCampoTerceiros('campo-terceiros-encarregados', 'terceiros_num_encarregados');
      limparCampoTerceiros('campo-terceiros-op-maquina', 'terceiros_num_op_maquina');
      limparCampoTerceiros('campo-terceiros-ajudantes', 'terceiros_num_ajudantes');
      limparCampoTerceiros('campo-terceiros-motorista', 'terceiros_num_motorista');
      limparCampoTerceiros('campo-terceiros-volume', 'terceiros_volume');
    }

    // 30/07/2026: a area do(s) servico(s) selecionado(s) pode mudar o
    // limite de fotos (Infra permite mais) -- reflete isso na tela
    // toda vez que a selecao de servicos mudar.
    atualizarLimitesDeFotoNaTela();
  }

  renderizarServicosAgrupados(
    listaServicosEl,
    servicos,
    rascunho.servicos,
    function () {
      atualizarVisibilidadeServicos();
      salvarRascunhoAgora();
    }
  );
  atualizarVisibilidadeServicos();

  campoOutrosServicoDesc.value = rascunho.outros_servico_desc || '';
  campoOutrosServicoDesc.addEventListener('input', function () {
    rascunho.outros_servico_desc = campoOutrosServicoDesc.value;
    salvarRascunhoAgora();
  });

  function ligarCampoNumericoTerceiros(elementoId, chaveRascunho) {
    const elemento = document.getElementById(elementoId);
    elemento.value = rascunho[chaveRascunho] || '';
    elemento.addEventListener('input', function () {
      elemento.value = elemento.value.replace(/\D/g, '').slice(0, 3);
      rascunho[chaveRascunho] = elemento.value;
      salvarRascunhoAgora();
    });
  }
  ligarCampoNumericoTerceiros('campo-terceiros-encarregados', 'terceiros_num_encarregados');
  ligarCampoNumericoTerceiros('campo-terceiros-op-maquina', 'terceiros_num_op_maquina');
  ligarCampoNumericoTerceiros('campo-terceiros-ajudantes', 'terceiros_num_ajudantes');
  ligarCampoNumericoTerceiros('campo-terceiros-motorista', 'terceiros_num_motorista');
  ligarCampoNumericoTerceiros('campo-terceiros-volume', 'terceiros_volume');

  const colaboradoresCadastro = await RadDB.obterCatalogo('colaboradores_cadastro');

  const listaColaboradoresEl = document.getElementById('lista-colaboradores-adicionados');
  const mensagemSemColaboradores = document.getElementById('mensagem-sem-colaboradores');
  const avisoColaboradores = document.getElementById('aviso-colaboradores');
  const blocoBuscaColaborador = document.getElementById('bloco-busca-colaborador');
  const campoBuscaColaborador = document.getElementById('campo-busca-colaborador');
  const resultadosBuscaColaborador = document.getElementById('resultados-busca-colaborador');
  const blocoNovoParticipante = document.getElementById('bloco-novo-participante');
  const campoNomeParticipante = document.getElementById('campo-nome-participante');

  function renderizarColaboradoresAdicionados() {
    listaColaboradoresEl.innerHTML = '';
    mensagemSemColaboradores.style.display = rascunho.colaboradores.length === 0 ? '' : 'none';

    rascunho.colaboradores.forEach(function (pessoa, indice) {
      const linha = document.createElement('div');
      linha.className = 'cartao';
      linha.style.padding = '0.75rem 1rem';
      linha.style.display = 'flex';
      linha.style.justifyContent = 'space-between';
      linha.style.alignItems = 'center';

      const rotuloTipo = pessoa.tipo === 'colaborador' ? 'Colaborador' : 'Participante';
      const registro = pessoa.registro_empresa ? ` · Registro ${pessoa.registro_empresa}` : '';
      linha.innerHTML = `
        <div>
          <strong>${pessoa.nome}</strong>
          <div class="texto-suave" style="font-size:0.8rem;">${rotuloTipo}${registro}</div>
        </div>
      `;

      const botaoRemover = document.createElement('button');
      botaoRemover.type = 'button';
      botaoRemover.className = 'botao botao--perigo';
      botaoRemover.style.width = 'auto';
      botaoRemover.style.minHeight = '36px';
      botaoRemover.style.padding = '0 0.9rem';
      botaoRemover.textContent = 'Remover';
      botaoRemover.addEventListener('click', function () {
        rascunho.colaboradores.splice(indice, 1);
        renderizarColaboradoresAdicionados();
        salvarRascunhoAgora();
      });
      linha.appendChild(botaoRemover);

      listaColaboradoresEl.appendChild(linha);
    });
  }
  renderizarColaboradoresAdicionados();

  function jaAdicionado(registroEmpresa) {
    return rascunho.colaboradores.some((p) => p.registro_empresa === registroEmpresa);
  }

  function adicionarPessoa(pessoa) {
    rascunho.colaboradores.push(pessoa);
    renderizarColaboradoresAdicionados();
    salvarRascunhoAgora();
  }

  document.getElementById('botao-adicionar-colaborador').addEventListener('click', function () {
    avisoColaboradores.innerHTML = '';
    blocoNovoParticipante.style.display = 'none';
    blocoBuscaColaborador.style.display = '';
    campoBuscaColaborador.value = '';
    resultadosBuscaColaborador.innerHTML = '';
    campoBuscaColaborador.focus();
  });

  document.getElementById('botao-adicionar-participante').addEventListener('click', function () {
    avisoColaboradores.innerHTML = '';
    blocoBuscaColaborador.style.display = 'none';
    blocoNovoParticipante.style.display = '';
    campoNomeParticipante.value = '';
    campoNomeParticipante.focus();
  });

  campoBuscaColaborador.addEventListener('input', function () {
    const termo = campoBuscaColaborador.value.trim().toLowerCase();
    resultadosBuscaColaborador.innerHTML = '';
    if (!termo) return;

    const encontrados = colaboradoresCadastro.filter(
      (c) =>
        c.registro_empresa.toLowerCase().includes(termo) || c.nome.toLowerCase().includes(termo)
    ).slice(0, 8);

    if (encontrados.length === 0) {
      const aviso = document.createElement('p');
      aviso.className = 'texto-suave';
      aviso.style.fontSize = '0.85rem';
      aviso.textContent = 'Colaborador não localizado.';
      resultadosBuscaColaborador.appendChild(aviso);
      return;
    }

    encontrados.forEach(function (candidato) {
      const botao = document.createElement('button');
      botao.type = 'button';
      botao.className = 'botao botao--secundaria';
      botao.style.textAlign = 'left';
      botao.style.justifyContent = 'flex-start';
      botao.textContent = `${candidato.registro_empresa} — ${candidato.nome}`;
      botao.addEventListener('click', function () {
        if (jaAdicionado(candidato.registro_empresa)) {
          avisoColaboradores.innerHTML =
            '<div class="aviso aviso--atencao">Este colaborador já foi adicionado a este RAD.</div>';
          return;
        }
        adicionarPessoa({
          registro_empresa: candidato.registro_empresa,
          nome: candidato.nome,
          tipo: 'colaborador',
        });
        avisoColaboradores.innerHTML = '';
        blocoBuscaColaborador.style.display = 'none';
      });
      resultadosBuscaColaborador.appendChild(botao);
    });
  });

  document.getElementById('botao-confirmar-participante').addEventListener('click', function () {
    const nome = campoNomeParticipante.value.trim();
    if (!nome) {
      avisoColaboradores.innerHTML =
        '<div class="aviso aviso--erro">Informe o nome do participante.</div>';
      return;
    }
    adicionarPessoa({ registro_empresa: null, nome: nome, tipo: 'participante' });
    avisoColaboradores.innerHTML = '';
    blocoNovoParticipante.style.display = 'none';
  });

  // 30/07/2026: registra os "atualizadores" de cada grupo de anexo com
  // limite dinamico, pra poder chama-los de novo quando a selecao de
  // servicos mudar (ex.: usuario marca um servico Infra depois de ja
  // ter aberto a tela -- o limite precisa refletir isso na hora).
  // (atualizadoresLimiteFoto, rotulos e funcoes ja declarados mais
  // acima, antes de atualizarVisibilidadeServicos.)

  function configurarGrupoAnexo(opcoes) {
    const {
      chave, inputEl, containerMiniaturasEl, avisoEl, obterLimite, validar, ehFoto,
    } = opcoes;

    function renderizarMiniaturas() {
      containerMiniaturasEl.innerHTML = '';
      rascunho.anexos[chave].forEach(function (arquivo, indice) {
        const item = document.createElement('div');
        item.className = 'cartao';
        item.style.padding = '0.6rem 0.8rem';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.gap = '0.75rem';

        if (ehFoto) {
          const img = document.createElement('img');
          img.src = URL.createObjectURL(arquivo);
          img.style.width = '48px';
          img.style.height = '48px';
          img.style.objectFit = 'cover';
          img.style.borderRadius = 'var(--raio-pequeno)';
          item.appendChild(img);
        }

        const nome = document.createElement('span');
        nome.style.flex = '1';
        nome.style.fontSize = '0.85rem';
        nome.style.overflow = 'hidden';
        nome.style.textOverflow = 'ellipsis';
        nome.style.whiteSpace = 'nowrap';
        nome.textContent = arquivo.name;
        item.appendChild(nome);

        const botaoRemover = document.createElement('button');
        botaoRemover.type = 'button';
        botaoRemover.className = 'botao botao--perigo';
        botaoRemover.style.width = 'auto';
        botaoRemover.style.minHeight = '36px';
        botaoRemover.style.padding = '0 0.9rem';
        botaoRemover.textContent = 'Remover';
        botaoRemover.addEventListener('click', function () {
          rascunho.anexos[chave].splice(indice, 1);
          renderizarMiniaturas();
          atualizarEstadoInput();
          salvarRascunhoAgora();
        });
        item.appendChild(botaoRemover);

        containerMiniaturasEl.appendChild(item);
      });
    }

    function atualizarEstadoInput() {
      const atingiuLimite = rascunho.anexos[chave].length >= obterLimite();
      inputEl.style.display = atingiuLimite ? 'none' : '';
    }

    inputEl.addEventListener('change', async function () {
      const arquivo = inputEl.files[0];
      inputEl.value = '';
      if (!arquivo) return;

      avisoEl.innerHTML = '';

      const limiteAtual = obterLimite();
      if (rascunho.anexos[chave].length >= limiteAtual) {
        avisoEl.innerHTML = `<div class="aviso aviso--erro">Limite de ${limiteAtual} atingido.</div>`;
        return;
      }

      const erro = await validar(arquivo);
      if (erro) {
        avisoEl.innerHTML = `<div class="aviso aviso--erro">${erro}</div>`;
        return;
      }

      rascunho.anexos[chave].push(arquivo);
      renderizarMiniaturas();
      atualizarEstadoInput();
      salvarRascunhoAgora();
    });

    renderizarMiniaturas();
    atualizarEstadoInput();
    atualizadoresLimiteFoto.push(atualizarEstadoInput);
  }

  configurarGrupoAnexo({
    chave: 'fotos_intervencao_verificada',
    inputEl: document.getElementById('campo-foto-intervencao'),
    containerMiniaturasEl: document.getElementById('miniaturas-fotos-intervencao'),
    avisoEl: document.getElementById('aviso-fotos-intervencao'),
    obterLimite: function () { return limiteFotoAtual('intervencao_verificada'); },
    validar: ValidadoresArquivos.validarFoto,
    ehFoto: true,
  });

  configurarGrupoAnexo({
    chave: 'fotos_acao_realizada',
    inputEl: document.getElementById('campo-foto-acao'),
    containerMiniaturasEl: document.getElementById('miniaturas-fotos-acao'),
    avisoEl: document.getElementById('aviso-fotos-acao'),
    obterLimite: function () { return limiteFotoAtual('acao_realizada'); },
    validar: ValidadoresArquivos.validarFoto,
    ehFoto: true,
  });

  atualizarRotulosLimiteFoto();

  configurarGrupoAnexo({
    chave: 'pdf',
    inputEl: document.getElementById('campo-pdf'),
    containerMiniaturasEl: document.getElementById('miniatura-pdf'),
    avisoEl: document.getElementById('aviso-pdf'),
    obterLimite: function () { return ValidadoresArquivos.LIMITE_PDF; },
    validar: ValidadoresArquivos.validarPdf,
    ehFoto: false,
  });

  // 30/07/2026: Comentarios das fotos -- 4 botoes ("Foto 1".."Foto 4"),
  // cada um abre/fecha uma caixa de texto propria (desc_foto_1..4).
  // Mesmos campos que ja existiam so para VPM001 (22/07/2026) -- agora
  // sempre disponiveis, com obrigatoriedade condicional:
  //   - VPM001 selecionado: os 4 ficam sempre abertos e obrigatorios,
  //     sem poder fechar (a exigencia e imposta no backend por
  //     VLD-033, mas a tela ja deixa isso visualmente claro).
  //   - Qualquer outro Tipo de Manutencao: cada botao liga/desliga sua
  //     caixa independentemente, tudo opcional.
  const ROTULOS_COMENTARIO_FOTO = {
    desc_foto_1: 'Foto 1',
    desc_foto_2: 'Foto 2',
    desc_foto_3: 'Foto 3',
    desc_foto_4: 'Foto 4',
  };
  const botoesComentariosFotos = document.getElementById('botoes-comentarios-fotos');
  const camposComentariosFotos = document.getElementById('campos-comentarios-fotos');
  const rotuloComentariosObrigatorio = document.getElementById('rotulo-comentarios-fotos-obrigatorio');

  // Estado de "aberto/fechado" de cada caixa, independente de ter
  // texto -- assim reabrir a tela mantem visivel um campo que a
  // pessoa abriu mas ainda nao escreveu nada.
  const comentarioFotoAberto = {
    desc_foto_1: !!rascunho.desc_foto_1,
    desc_foto_2: !!rascunho.desc_foto_2,
    desc_foto_3: !!rascunho.desc_foto_3,
    desc_foto_4: !!rascunho.desc_foto_4,
  };

  function atualizarComentariosFotos() {
    const obrigatorio = ehVpm001Selecionado();
    rotuloComentariosObrigatorio.textContent = obrigatorio ? '(obrigatório — Tipo de Manutenção VPM001)' : '(opcional)';
    rotuloComentariosObrigatorio.className = obrigatorio ? 'obrigatorio' : 'texto-suave';

    botoesComentariosFotos.innerHTML = '';
    camposComentariosFotos.innerHTML = '';

    Object.keys(ROTULOS_COMENTARIO_FOTO).forEach(function (chave) {
      const aberto = obrigatorio ? true : comentarioFotoAberto[chave];

      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.textContent = ROTULOS_COMENTARIO_FOTO[chave];
      chip.setAttribute('aria-pressed', aberto ? 'true' : 'false');
      if (obrigatorio) chip.disabled = true; // nao da pra fechar um campo obrigatorio
      chip.addEventListener('click', function () {
        if (obrigatorio) return;
        comentarioFotoAberto[chave] = !comentarioFotoAberto[chave];
        if (!comentarioFotoAberto[chave]) {
          rascunho[chave] = '';
          salvarRascunhoAgora();
        }
        atualizarComentariosFotos();
      });
      botoesComentariosFotos.appendChild(chip);

      if (aberto) {
        const grupoCampo = document.createElement('div');
        grupoCampo.style.marginTop = '0.5rem';
        const rotulo = document.createElement('label');
        rotulo.textContent = `Comentário — ${ROTULOS_COMENTARIO_FOTO[chave]}`;
        rotulo.style.fontSize = '0.85rem';
        const textarea = document.createElement('textarea');
        textarea.maxLength = 1000;
        textarea.value = rascunho[chave] || '';
        textarea.addEventListener('input', function () {
          rascunho[chave] = textarea.value;
          salvarRascunhoAgora();
        });
        grupoCampo.appendChild(rotulo);
        grupoCampo.appendChild(textarea);
        camposComentariosFotos.appendChild(grupoCampo);
      }
    });
  }
  atualizarComentariosFotos();

  function ligarCampoTexto(elementoId, chaveRascunho) {
    const elemento = document.getElementById(elementoId);
    elemento.value = rascunho[chaveRascunho] || '';
    elemento.addEventListener('input', function () {
      rascunho[chaveRascunho] = elemento.value;
      salvarRascunhoAgora();
    });
  }

  function configurarSugestaoResponsavel(inputEl, resultadosEl, chaveRascunho) {
    inputEl.value = rascunho[chaveRascunho] || '';

    inputEl.addEventListener('input', function () {
      rascunho[chaveRascunho] = inputEl.value;
      salvarRascunhoAgora();

      const termo = inputEl.value.trim().toLowerCase();
      resultadosEl.innerHTML = '';
      if (!termo) return;

      const encontrados = colaboradoresCadastro
        .filter((pessoa) => pessoa.nome.toLowerCase().includes(termo))
        .slice(0, 8);

      encontrados.forEach(function (pessoa) {
        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'botao botao--secundaria';
        botao.style.textAlign = 'left';
        botao.style.justifyContent = 'flex-start';
        botao.textContent = pessoa.nome;
        botao.addEventListener('click', function () {
          inputEl.value = pessoa.nome;
          rascunho[chaveRascunho] = pessoa.nome;
          resultadosEl.innerHTML = '';
          salvarRascunhoAgora();
        });
        resultadosEl.appendChild(botao);
      });
    });

    inputEl.addEventListener('blur', function () {
      setTimeout(function () {
        resultadosEl.innerHTML = '';
      }, 150);
    });
  }

  configurarSugestaoResponsavel(
    document.getElementById('campo-responsavel-atividade'),
    document.getElementById('resultados-responsavel-atividade'),
    'responsavel_atividade'
  );
  // Operador CCM (30/07/2026): dois pares Nome+Hora -- Abertura e
  // Entrega. Regra: o nome digitado na Abertura preenche
  // automaticamente a Entrega, mas o usuario pode editar a Entrega
  // depois -- a partir dai, o auto-preenchimento para (mesmo padrao
  // ja usado para a data de termino em recalcularHorarios acima).
  const campoCcmAberturaNome = document.getElementById('campo-operador-ccm-abertura-nome');
  const campoCcmAberturaHora = document.getElementById('campo-operador-ccm-abertura-hora');
  const campoCcmEntregaNome = document.getElementById('campo-operador-ccm-entrega-nome');
  const campoCcmEntregaHora = document.getElementById('campo-operador-ccm-entrega-hora');

  campoCcmAberturaNome.value = rascunho.operador_ccm_abertura_nome || '';
  campoCcmAberturaHora.value = rascunho.operador_ccm_abertura_hora || '00:00';
  campoCcmEntregaNome.value = rascunho.operador_ccm_entrega_nome || '';
  campoCcmEntregaHora.value = rascunho.operador_ccm_entrega_hora || '00:00';

  let ccmEntregaNomeEditadoManualmente = !!rascunho._operadorCcmEntregaNomeEditado;

  campoCcmAberturaNome.addEventListener('input', function () {
    rascunho.operador_ccm_abertura_nome = campoCcmAberturaNome.value;
    if (!ccmEntregaNomeEditadoManualmente) {
      rascunho.operador_ccm_entrega_nome = campoCcmAberturaNome.value;
      campoCcmEntregaNome.value = campoCcmAberturaNome.value;
    }
    salvarRascunhoAgora();
  });

  campoCcmAberturaHora.addEventListener('change', function () {
    rascunho.operador_ccm_abertura_hora = campoCcmAberturaHora.value || '00:00';
    salvarRascunhoAgora();
  });

  campoCcmEntregaNome.addEventListener('input', function () {
    ccmEntregaNomeEditadoManualmente = true;
    rascunho._operadorCcmEntregaNomeEditado = true;
    rascunho.operador_ccm_entrega_nome = campoCcmEntregaNome.value;
    salvarRascunhoAgora();
  });

  campoCcmEntregaHora.addEventListener('change', function () {
    rascunho.operador_ccm_entrega_hora = campoCcmEntregaHora.value || '00:00';
    salvarRascunhoAgora();
  });

  ligarCampoTexto('campo-descricao-tecnica', 'descricao_tecnica_atividade');
  ligarCampoTexto('campo-tipo-veiculo', 'tipo_veiculo');
  ligarCampoTexto('campo-operador', 'operador');
  ligarCampoTexto('campo-materiais-utilizados', 'materiais_utilizados');
  ligarCampoTexto('campo-observacoes-gerais', 'observacoes_gerais');

  let sincronizando = false;

  const botaoSincronizar = document.getElementById('botao-sincronizar');
  const textoStatusBotao = document.getElementById('texto-status-botao');
  const avisoSincronizacao = document.getElementById('aviso-sincronizacao');
  const listaErrosSincronizacao = document.getElementById('lista-erros-sincronizacao');

  function atualizarEstadoBotaoSincronizar() {
    if (sincronizando) {
      botaoSincronizar.disabled = true;
      botaoSincronizar.textContent = 'Sincronizando…';
      textoStatusBotao.textContent = '';
    } else if (!navigator.onLine) {
      botaoSincronizar.disabled = true;
      botaoSincronizar.textContent = 'Sincronizar';
      textoStatusBotao.textContent = 'Sem conexão';
    } else {
      botaoSincronizar.disabled = false;
      botaoSincronizar.textContent = 'Sincronizar';
      textoStatusBotao.textContent = '';
    }
  }
  atualizarEstadoBotaoSincronizar();
  window.addEventListener('online', atualizarEstadoBotaoSincronizar);
  window.addEventListener('offline', atualizarEstadoBotaoSincronizar);
  atualizarEstadoBotaoExportar();

  const modalExportar = document.getElementById('modal-exportar');
  const avisoExportarRascunho = document.getElementById('aviso-exportar-rascunho');

  function avisarCamposFaltando() {
    const faltando = ExportarCliente.camposObrigatoriosFaltando(rascunho);
    avisoExportarRascunho.innerHTML =
      '<div class="aviso aviso--erro">Preencha os campos obrigatórios antes de continuar: ' +
      faltando.join(', ') + '.</div>';
  }

  document.getElementById('botao-exportar').addEventListener('click', function () {
    if (!ExportarCliente.camposObrigatoriosPreenchidos(rascunho)) {
      avisarCamposFaltando();
      return;
    }
    modalExportar.style.display = 'flex';
  });
  document.getElementById('botao-fechar-exportar').addEventListener('click', function () {
    modalExportar.style.display = 'none';
  });

  function catalogosParaExportar() {
    return {
      locais, linhas, vias, equipes,
      tipos_manutencao: tiposManutencao,
      servicos,
      mch: mchs,
      motivos_atraso: motivosAtraso,
      colaboradores_cadastro: colaboradoresCadastro,
    };
  }

  function baixarBlob(blob, nomeArquivo) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = nomeArquivo;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  document.getElementById('botao-copiar-mensagem').addEventListener('click', async function () {
    if (!ExportarCliente.camposObrigatoriosPreenchidos(rascunho)) {
      avisarCamposFaltando();
      return;
    }
    try {
      const mensagem = ExportarCliente.gerarMensagemCopiar(rascunho, catalogosParaExportar());
      await navigator.clipboard.writeText(mensagem);
      avisoExportarRascunho.innerHTML = '<div class="aviso aviso--sucesso">Mensagem copiada para a área de transferência.</div>';
    } catch (erro) {
      avisoExportarRascunho.innerHTML = '<div class="aviso aviso--erro">Não foi possível copiar a mensagem.</div>';
    }
  });

  document.getElementById('botao-exportar-pdf').addEventListener('click', function () {
    try {
      const nomeArquivo = `RAD_OS${rascunho.numero_os || 'rascunho'}.pdf`;
      const blob = ExportarCliente.gerarPdfBlob(rascunho, catalogosParaExportar());
      baixarBlob(blob, nomeArquivo);
      modalExportar.style.display = 'none';
    } catch (erro) {
      avisoExportarRascunho.innerHTML = '<div class="aviso aviso--erro">Não foi possível gerar o PDF.</div>';
    }
  });

  document.getElementById('botao-exportar-docx').addEventListener('click', function () {
    try {
      const nomeArquivo = `RAD_OS${rascunho.numero_os || 'rascunho'}.doc`;
      const blob = ExportarCliente.gerarDocxBlob(rascunho, catalogosParaExportar());
      baixarBlob(blob, nomeArquivo);
      modalExportar.style.display = 'none';
    } catch (erro) {
      avisoExportarRascunho.innerHTML = '<div class="aviso aviso--erro">Não foi possível gerar o arquivo Word.</div>';
    }
  });

  function montarDadosParaEnvio() {
    return {
      numero_os: rascunho.numero_os,
      numero_sa: rascunho.numero_sa,
      solicitante_sa: rascunho.solicitante_sa,
      data_preenchimento: rascunho.data_preenchimento,
      id_local_inicial: rascunho.id_local_inicial,
      id_local_final: rascunho.id_local_final,
      linhas: rascunho.linhas,
      vias: rascunho.vias,
      equipes: rascunho.equipes,
      km_poste: rascunho.km_poste,
      tipo_veiculo: rascunho.tipo_veiculo,
      operador: rascunho.operador,
      id_tipo_manutencao: rascunho.id_tipo_manutencao,
      numero_falha: rascunho.numero_falha,
      hora_prog_inicio: rascunho.hora_prog_inicio,
      data_hp_inicio: rascunho.data_hp_inicio,
      hora_prog_termino: rascunho.hora_prog_termino,
      data_hp_termino: rascunho.data_hp_termino,
      hora_real_inicio: rascunho.hora_real_inicio,
      data_hr_inicio: rascunho.data_hr_inicio,
      hora_real_termino: rascunho.hora_real_termino,
      data_hr_termino: rascunho.data_hr_termino,
      id_motivo_atraso_termino: rascunho.id_motivo_atraso_termino,
      desc_motivo_atraso_termino: rascunho.desc_motivo_atraso_termino,
      servicos: rascunho.servicos,
      outros_servico_desc: rascunho.outros_servico_desc,
      desc_foto_1: rascunho.desc_foto_1,
      desc_foto_2: rascunho.desc_foto_2,
      desc_foto_3: rascunho.desc_foto_3,
      desc_foto_4: rascunho.desc_foto_4,
      terceiros_num_encarregados: rascunho.terceiros_num_encarregados ? Number(rascunho.terceiros_num_encarregados) : null,
      terceiros_num_op_maquina: rascunho.terceiros_num_op_maquina ? Number(rascunho.terceiros_num_op_maquina) : null,
      terceiros_num_ajudantes: rascunho.terceiros_num_ajudantes ? Number(rascunho.terceiros_num_ajudantes) : null,
      terceiros_num_motorista: rascunho.terceiros_num_motorista ? Number(rascunho.terceiros_num_motorista) : null,
      terceiros_volume: rascunho.terceiros_volume ? Number(rascunho.terceiros_volume) : null,
      amv_blocos: rascunho.amv_blocos,
      colaboradores: rascunho.colaboradores,
      responsavel_atividade: rascunho.responsavel_atividade,
      operador_ccm_abertura_nome: rascunho.operador_ccm_abertura_nome,
      operador_ccm_abertura_hora: rascunho.operador_ccm_abertura_hora,
      operador_ccm_entrega_nome: rascunho.operador_ccm_entrega_nome,
      operador_ccm_entrega_hora: rascunho.operador_ccm_entrega_hora,
      descricao_tecnica_atividade: rascunho.descricao_tecnica_atividade,
      materiais_utilizados: rascunho.materiais_utilizados,
      observacoes_gerais: rascunho.observacoes_gerais,
      sync_id_tentativa: rascunho.sync_id_tentativa,
    };
  }

  function renderizarErrosSincronizacao(erros) {
    const itens = erros
      .map((e) => `<li>${e.mensagem || e.campo}</li>`)
      .join('');
    listaErrosSincronizacao.innerHTML = `
      <div class="aviso aviso--erro">
        <strong>Não foi possível sincronizar. Corrija os itens abaixo:</strong>
        <ul style="margin: 0.5rem 0 0; padding-left: 1.2rem;">${itens}</ul>
      </div>
    `;
    listaErrosSincronizacao.scrollIntoView && listaErrosSincronizacao.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  botaoSincronizar.addEventListener('click', async function () {
    if (sincronizando || !navigator.onLine) return;

    sincronizando = true;
    atualizarEstadoBotaoSincronizar();
    listaErrosSincronizacao.innerHTML = '';
    avisoSincronizacao.innerHTML = '';

    try {
      const formData = new FormData();
      formData.append('dados', JSON.stringify(montarDadosParaEnvio()));
      rascunho.anexos.fotos_intervencao_verificada.forEach((arquivo) => {
        formData.append('fotos_intervencao_verificada', arquivo);
      });
      rascunho.anexos.fotos_acao_realizada.forEach((arquivo) => {
        formData.append('fotos_acao_realizada', arquivo);
      });
      rascunho.anexos.pdf.forEach((arquivo) => {
        formData.append('pdf', arquivo);
      });

      const resposta = await RadAuth.requisicaoAutenticada('/rad/sincronizar/', {
        method: 'POST',
        body: formData,
      });

      if (resposta.status === 201 || resposta.status === 200) {
        await RadDB.limparRascunho(sessao.login);
        avisoSincronizacao.innerHTML =
          '<div class="aviso aviso--sucesso">RAD sincronizado com sucesso!</div>';
        setTimeout(function () {
          window.location.href = '/inicio/';
        }, 1200);
        return;
      }

      if (resposta.status === 422) {
        const corpo = await resposta.json();
        renderizarErrosSincronizacao(corpo.erros || []);
      } else {
        const corpo = await resposta.json().catch(() => ({}));
        renderizarErrosSincronizacao([
          { mensagem: corpo.erro || 'Erro inesperado ao sincronizar. Tente novamente.' },
        ]);
      }
    } catch (erro) {
      renderizarErrosSincronizacao([
        { mensagem: 'Erro de conexão durante a sincronização. Seus dados continuam salvos neste dispositivo — tente novamente.' },
      ]);
    } finally {
      sincronizando = false;
      atualizarEstadoBotaoSincronizar();
    }
  });

});
