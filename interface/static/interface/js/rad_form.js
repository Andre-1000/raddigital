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
  if (!rascunho.amv) {
    rascunho.amv = { id_mch: null, tipos_defeito: [], acoes: [], desc_outros_tipo_defeito: '', desc_outros_acao: '' };
  }
  if (!('desc_outros_tipo_defeito' in rascunho.amv)) rascunho.amv.desc_outros_tipo_defeito = '';
  if (!('desc_outros_acao' in rascunho.amv)) rascunho.amv.desc_outros_acao = '';
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
      amv: { id_mch: null, tipos_defeito: [], acoes: [], desc_outros_tipo_defeito: '', desc_outros_acao: '' },
      colaboradores: [],
      anexos: {
        fotos_intervencao_verificada: [],
        fotos_acao_realizada: [],
        pdf: [],
      },
      responsavel_atividade: '',
      operador_ccm: '',
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

  // 22/07/2026: VPM001 abre 4 caixas de descricao de foto (1000
  // caracteres cada), 2 abaixo de cada grupo de fotos (Intervencao
  // Verificada: 1/2, Acao Realizada: 3/4).
  const blocoDescFotosIntervencao = document.getElementById('bloco-desc-fotos-intervencao');
  const blocoDescFotosAcao = document.getElementById('bloco-desc-fotos-acao');
  const camposDescFoto = {
    desc_foto_1: document.getElementById('campo-desc-foto-1'),
    desc_foto_2: document.getElementById('campo-desc-foto-2'),
    desc_foto_3: document.getElementById('campo-desc-foto-3'),
    desc_foto_4: document.getElementById('campo-desc-foto-4'),
  };
  Object.keys(camposDescFoto).forEach(function (chave) {
    const elemento = camposDescFoto[chave];
    elemento.value = rascunho[chave] || '';
    elemento.addEventListener('input', function () {
      rascunho[chave] = elemento.value;
      salvarRascunhoAgora();
    });
  });

  function ehVpm001Selecionado() {
    return nomeDoTipoSelecionado() === 'VPM001';
  }

  function atualizarVisibilidadeDescFotos() {
    const mostrar = ehVpm001Selecionado();
    blocoDescFotosIntervencao.style.display = mostrar ? '' : 'none';
    blocoDescFotosAcao.style.display = mostrar ? '' : 'none';
    if (!mostrar) {
      Object.keys(camposDescFoto).forEach(function (chave) {
        rascunho[chave] = '';
        camposDescFoto[chave].value = '';
      });
    }
  }
  atualizarVisibilidadeDescFotos();

  campoTipoManutencao.addEventListener('change', function () {
    rascunho.id_tipo_manutencao = campoTipoManutencao.value ? Number(campoTipoManutencao.value) : null;
    atualizarVisibilidadeNumeroFalha();
    atualizarVisibilidadeDescFotos();
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

  // 30/07/2026: variante de renderizarListaCheckbox especifica para
  // Servicos Executados -- agrupa visualmente em "Geral" e "Infra"
  // (usando o campo area vindo do catalogo), com "Outros" sempre por
  // ultimo, fora dos grupos. So muda a apresentacao; a logica de
  // selecao (checkbox marcado/desmarcado, callback aoMudar) e identica
  // a renderizarListaCheckbox.
  function renderizarServicosAgrupados(containerEl, servicosOrdenados, valoresSelecionados, aoMudar) {
    containerEl.innerHTML = '';

    function adicionarCabecalho(texto) {
      const cabecalho = document.createElement('p');
      cabecalho.className = 'grade-checkboxes__cabecalho';
      cabecalho.textContent = texto;
      containerEl.appendChild(cabecalho);
    }

    function adicionarItens(itens) {
      itens.forEach(function (servico) {
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
        containerEl.appendChild(linha);
      });
    }

    const outros = servicosOrdenados.filter((s) => s.nome === 'Outros');
    const grupos = [
      { rotulo: 'Geral', itens: servicosOrdenados.filter((s) => s.area !== 'infra' && s.nome !== 'Outros') },
      { rotulo: 'Infra', itens: servicosOrdenados.filter((s) => s.area === 'infra') },
    ];

    grupos.forEach(function (grupo) {
      if (grupo.itens.length === 0) return;
      adicionarCabecalho(grupo.rotulo);
      adicionarItens(grupo.itens);
    });

    if (outros.length > 0) {
      adicionarItens(outros);
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

  const campoMch = document.getElementById('campo-mch');
  const listaMchEl = document.getElementById('lista-mch');
  const detalhesMch = document.getElementById('detalhes-mch');
  const mapaMchPorRotulo = new Map();

  mchs.forEach(function (mch) {
    mapaMchPorRotulo.set(mch.identificacao, mch.id);
    const opcao = document.createElement('option');
    opcao.value = mch.identificacao;
    listaMchEl.appendChild(opcao);
  });

  function preencherDetalhesMch(idMch) {
    const mch = mchs.find((m) => m.id === idMch);
    if (!mch) {
      detalhesMch.style.display = 'none';
      return;
    }
    document.getElementById('valor-mch-modelo').textContent = mch.modelo || '—';
    document.getElementById('valor-mch-via').textContent = mch.via || '—';
    document.getElementById('valor-mch-ur').textContent = mch.ur || '—';
    document.getElementById('valor-mch-local').textContent = mch.local_amv || '—';
    document.getElementById('valor-mch-linha').textContent = mch.linha || '—';
    detalhesMch.style.display = 'flex';
  }

  const campoGrupoOutrosDefeito = document.getElementById('campo-grupo-outros-defeito');
  const campoDescOutrosDefeito = document.getElementById('campo-desc-outros-defeito');
  const campoGrupoOutrosAcao = document.getElementById('campo-grupo-outros-acao');
  const campoDescOutrosAcao = document.getElementById('campo-desc-outros-acao');

  campoDescOutrosDefeito.value = rascunho.amv.desc_outros_tipo_defeito || '';
  campoDescOutrosDefeito.addEventListener('input', function () {
    rascunho.amv.desc_outros_tipo_defeito = campoDescOutrosDefeito.value;
    salvarRascunhoAgora();
  });
  campoDescOutrosAcao.value = rascunho.amv.desc_outros_acao || '';
  campoDescOutrosAcao.addEventListener('input', function () {
    rascunho.amv.desc_outros_acao = campoDescOutrosAcao.value;
    salvarRascunhoAgora();
  });

  function atualizarVisibilidadeOutrosAmv() {
    const defeitoOutrosSelecionado = tiposDefeitoAmv.some(
      (t) => t.requer_descricao && rascunho.amv.tipos_defeito.includes(t.id)
    );
    campoGrupoOutrosDefeito.style.display = defeitoOutrosSelecionado ? '' : 'none';
    if (!defeitoOutrosSelecionado) {
      rascunho.amv.desc_outros_tipo_defeito = '';
      campoDescOutrosDefeito.value = '';
    }

    const acaoOutrosSelecionada = acoesAmv.some(
      (a) => a.requer_descricao && rascunho.amv.acoes.includes(a.id)
    );
    campoGrupoOutrosAcao.style.display = acaoOutrosSelecionada ? '' : 'none';
    if (!acaoOutrosSelecionada) {
      rascunho.amv.desc_outros_acao = '';
      campoDescOutrosAcao.value = '';
    }
  }

  function renderizarBlocoAmv() {
    campoMch.value = rascunho.amv.id_mch ? (mchs.find((m) => m.id === rascunho.amv.id_mch) || {}).identificacao || '' : '';
    preencherDetalhesMch(rascunho.amv.id_mch);

    renderizarListaCheckbox(
      document.getElementById('lista-tipos-defeito'),
      tiposDefeitoAmv.map((t) => ({ valor: t.id, rotulo: t.nome })),
      rascunho.amv.tipos_defeito,
      function () {
        atualizarVisibilidadeOutrosAmv();
        salvarRascunhoAgora();
      }
    );
    renderizarListaCheckbox(
      document.getElementById('lista-acoes-amv'),
      acoesAmv.map((a) => ({ valor: a.id, rotulo: a.nome })),
      rascunho.amv.acoes,
      function () {
        atualizarVisibilidadeOutrosAmv();
        salvarRascunhoAgora();
      }
    );
    atualizarVisibilidadeOutrosAmv();
  }

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
      renderizarBlocoAmv();
    } else {
      blocoAmv.style.display = 'none';
      rascunho.amv.id_mch = null;
      rascunho.amv.tipos_defeito.length = 0;
      rascunho.amv.acoes.length = 0;
      rascunho.amv.desc_outros_tipo_defeito = '';
      rascunho.amv.desc_outros_acao = '';
      campoMch.value = '';
      detalhesMch.style.display = 'none';
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

  campoMch.addEventListener('change', function () {
    const idMch = mapaMchPorRotulo.get(campoMch.value.trim());
    rascunho.amv.id_mch = idMch || null;
    preencherDetalhesMch(idMch);
    salvarRascunhoAgora();
  });

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

  function configurarGrupoAnexo(opcoes) {
    const {
      chave, inputEl, containerMiniaturasEl, avisoEl, limite, validar, ehFoto,
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
      const atingiuLimite = rascunho.anexos[chave].length >= limite;
      inputEl.style.display = atingiuLimite ? 'none' : '';
    }

    inputEl.addEventListener('change', async function () {
      const arquivo = inputEl.files[0];
      inputEl.value = '';
      if (!arquivo) return;

      avisoEl.innerHTML = '';

      if (rascunho.anexos[chave].length >= limite) {
        avisoEl.innerHTML = `<div class="aviso aviso--erro">Limite de ${limite} atingido.</div>`;
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
  }

  configurarGrupoAnexo({
    chave: 'fotos_intervencao_verificada',
    inputEl: document.getElementById('campo-foto-intervencao'),
    containerMiniaturasEl: document.getElementById('miniaturas-fotos-intervencao'),
    avisoEl: document.getElementById('aviso-fotos-intervencao'),
    limite: ValidadoresArquivos.LIMITE_FOTOS_POR_CATEGORIA,
    validar: ValidadoresArquivos.validarFoto,
    ehFoto: true,
  });

  configurarGrupoAnexo({
    chave: 'fotos_acao_realizada',
    inputEl: document.getElementById('campo-foto-acao'),
    containerMiniaturasEl: document.getElementById('miniaturas-fotos-acao'),
    avisoEl: document.getElementById('aviso-fotos-acao'),
    limite: ValidadoresArquivos.LIMITE_FOTOS_POR_CATEGORIA,
    validar: ValidadoresArquivos.validarFoto,
    ehFoto: true,
  });

  configurarGrupoAnexo({
    chave: 'pdf',
    inputEl: document.getElementById('campo-pdf'),
    containerMiniaturasEl: document.getElementById('miniatura-pdf'),
    avisoEl: document.getElementById('aviso-pdf'),
    limite: ValidadoresArquivos.LIMITE_PDF,
    validar: ValidadoresArquivos.validarPdf,
    ehFoto: false,
  });

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
  ligarCampoTexto('campo-operador-ccm', 'operador_ccm');
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
      amv: rascunho.amv,
      colaboradores: rascunho.colaboradores,
      responsavel_atividade: rascunho.responsavel_atividade,
      operador_ccm: rascunho.operador_ccm,
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
