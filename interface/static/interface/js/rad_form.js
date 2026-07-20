/*
 * Logica do formulario de preenchimento do RAD.
 *
 * Arquitetura: um unico objeto `rascunho` guarda o estado do
 * formulario inteiro, no MESMO formato que /rad/sincronizar/ espera
 * (ver rad/regras_negocio.py). Cada alteracao de campo atualiza
 * `rascunho` e chama salvarRascunhoAgora(), que grava no IndexedDB
 * (RadDB) -- e assim que o "salvamento a cada alteracao de campo" da
 * EFD 3.8 funciona neste bloco.
 *
 * Este arquivo cresce a cada bloco de trabalho (horarios, servicos,
 * colaboradores, anexos, sincronizacao). Nesta etapa (Bloco 1) ele
 * cobre Identificacao, Localizacao e Controle Operacional.
 */
document.addEventListener('DOMContentLoaded', async function () {
  if (!RadAuth.exigirSessao()) return;

  const sessao = RadAuth.obterSessao();
  document.getElementById('conteudo-protegido').style.display = '';

  const statusRascunho = document.getElementById('status-rascunho');
  const avisoFormulario = document.getElementById('aviso-formulario');

  // ---- Estado ---------------------------------------------------------

  let rascunho = await RadDB.obterRascunho(sessao.login);
  const jaExistiaRascunho = rascunho !== null;
  if (!rascunho) {
    rascunho = criarRascunhoVazio();
  } else {
    // Preenche com defaults quaisquer campos novos que ainda nao
    // existiam em rascunhos salvos por uma versao anterior do
    // formulario (o formulario cresce em blocos de trabalho).
    const padrao = criarRascunhoVazio();
    for (const chave in padrao) {
      if (!(chave in rascunho)) rascunho[chave] = padrao[chave];
    }
  }
  if (!rascunho.amv) {
    rascunho.amv = { id_mch: null, tipos_defeito: [], acoes: [] };
  }
  if (!rascunho.anexos) {
    rascunho.anexos = { fotos_intervencao_verificada: [], fotos_acao_realizada: [], pdf: [] };
  }

  // ---- Apagar rascunho (RG-SYNC-019/020/022) ------------------------------
  //
  // Precisa estar cabeado ANTES do gate de conflito abaixo (que pode
  // pausar a execucao do script com um await): o modal de conflito
  // reaproveita este mesmo modal de exclusao para a opcao "apagar e
  // comecar um novo" (RG-SYNC-019), entao os botoes precisam ja estar
  // ouvindo clique antes do usuario poder interagir com eles.
  //
  // Apos apagar, recarrega esta MESMA pagina -- assim tanto o botao
  // "Apagar rascunho" do topo quanto "apagar e comecar um novo" do
  // conflito terminam no mesmo lugar: um formulario limpo.

  let resolverConflitoPendente = null;
  const modalConfirmarExclusao = document.getElementById('modal-confirmar-exclusao');
  const modalConflitoRascunho = document.getElementById('modal-conflito-rascunho');

  document.getElementById('botao-apagar-rascunho').addEventListener('click', function () {
    modalConfirmarExclusao.style.display = 'flex';
  });
  document.getElementById('botao-cancelar-exclusao').addEventListener('click', function () {
    modalConfirmarExclusao.style.display = 'none';
    if (resolverConflitoPendente) {
      // Veio do modal de conflito e desistiu de apagar -- volta para
      // a pergunta original em vez de deixar a tela travada sem
      // nenhum modal e sem o formulario ter sido renderizado ainda.
      modalConflitoRascunho.style.display = 'flex';
    }
  });
  document.getElementById('botao-confirmar-exclusao').addEventListener('click', async function () {
    await RadDB.limparRascunho(sessao.login);
    window.location.reload();
  });

  // ---- Conflito: ja existe um RAD em preenchimento (RG-SYNC-018/019) -----
  //
  // So pergunta se o rascunho existente tem conteudo que valha a pena
  // preservar (RG-SYNC-018 fala em "RAD com status Rascunho Local" --
  // um rascunho recem-criado, ainda vazio, nao conta como "em
  // preenchimento" e perguntar aqui so atrapalharia).

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
        // resolverConflitoPendente continua setado -- se o usuario
        // cancelar a exclusao no proximo modal, volta para este.
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
      data_preenchimento: isoData,
      id_local_inicial: '',
      id_local_final: '',
      linhas: [],
      vias: [],
      equipes: ['VP'], // RG: VP sempre presente, ja vem marcada
      km_poste: '',
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
      id_motivo_atraso_inicio: null,
      desc_motivo_atraso_inicio: '',
      id_motivo_atraso_termino: null,
      desc_motivo_atraso_termino: '',
      servicos: [],
      outros_servico_desc: '',
      amv: { id_mch: null, tipos_defeito: [], acoes: [] },
      colaboradores: [], // [{registro_empresa, nome, tipo: 'colaborador'|'participante'}]
      anexos: {
        fotos_intervencao_verificada: [], // File[]
        fotos_acao_realizada: [], // File[]
        pdf: [], // File[] (no maximo 1, mas array por simetria com o payload)
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
    // Identificador local unico para esta tentativa de RAD (usado na
    // sincronizacao para idempotencia). Gerado uma vez, ao criar o
    // rascunho, e mantido ate sincronizar com sucesso.
    return 'rascunho-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
  }

  async function salvarRascunhoAgora() {
    await RadDB.salvarRascunho(sessao.login, rascunho);
    const agora = new Date();
    statusRascunho.textContent = `Salvo neste dispositivo às ${agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
    atualizarEstadoBotaoExportar();
  }

  // RG-EXP-005: botao de exportar so habilita com os obrigatorios
  // preenchidos. Verificado a cada salvamento (ou seja, a cada
  // alteracao de campo), reaproveitando o mesmo gancho do autosave.
  function atualizarEstadoBotaoExportar() {
    const botaoExportar = document.getElementById('botao-exportar');
    if (botaoExportar) {
      botaoExportar.disabled = !ExportarCliente.camposObrigatoriosPreenchidos(rascunho);
    }
  }

  // ---- Catalogos --------------------------------------------------------

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

  // ---- Local Inicial / Final (lista pesquisavel) -------------------------

  const listaLocaisEl = document.getElementById('lista-locais');
  const mapaLocaisPorRotulo = new Map(); // "BFU - Barra Funda" -> "BFU"

  locais.forEach(function (local) {
    const rotulo = `${local.sigla} - ${local.nome}`;
    mapaLocaisPorRotulo.set(rotulo, local.sigla);
    const opcao = document.createElement('option');
    opcao.value = rotulo;
    listaLocaisEl.appendChild(opcao);
  });

  function rotuloDoLocal(sigla) {
    const local = locais.find((l) => l.sigla === sigla);
    return local ? `${local.sigla} - ${local.nome}` : '';
  }

  function ligarCampoLocal(inputEl, chaveRascunho) {
    if (rascunho[chaveRascunho]) {
      inputEl.value = rotuloDoLocal(rascunho[chaveRascunho]);
    }
    inputEl.addEventListener('change', function () {
      const sigla = mapaLocaisPorRotulo.get(inputEl.value.trim());
      rascunho[chaveRascunho] = sigla || '';
      salvarRascunhoAgora();
    });
  }

  ligarCampoLocal(document.getElementById('campo-local-inicial'), 'id_local_inicial');
  ligarCampoLocal(document.getElementById('campo-local-final'), 'id_local_final');

  // ---- Chips: Linha, Via, Equipes ----------------------------------------

  /**
   * Renderiza um grupo de chips clicaveis (selecao multipla).
   * itens: lista de {valor, rotulo}.
   * valoresSelecionados: array (referencia direta do rascunho -- mutado in-place).
   * fixos: valores que nao podem ser desmarcados pelo usuario (ex.: VP).
   */
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
    ['VP'] // RG: VP e sempre incluida, nao pode ser desmarcada na tela
  );

  // ---- Km/Poste (mascara automatica, RG-LOC-007) -------------------------

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
    // So aplica a mascara automatica quando o usuario digitou apenas
    // numeros (RG-LOC-007) -- edicao manual livre continua permitida.
    const somenteDigitos = /^\d+$/.test(campoKmPoste.value.replace(/[/\s-]/g, ''));
    if (somenteDigitos) {
      campoKmPoste.value = aplicarMascaraKmPoste(campoKmPoste.value);
    }
    rascunho.km_poste = campoKmPoste.value;
    salvarRascunhoAgora();
  });

  // ---- Tipo de Manutencao + N Falha condicional --------------------------

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
      // RG-COP-009: ao sair de "Falha", limpa o numero da falha.
      campoNumeroFalha.value = '';
      rascunho.numero_falha = null;
    }
  }
  atualizarVisibilidadeNumeroFalha();

  campoTipoManutencao.addEventListener('change', function () {
    rascunho.id_tipo_manutencao = campoTipoManutencao.value ? Number(campoTipoManutencao.value) : null;
    atualizarVisibilidadeNumeroFalha();
    salvarRascunhoAgora();
  });

  campoNumeroFalha.addEventListener('input', function () {
    rascunho.numero_falha = campoNumeroFalha.value ? Number(campoNumeroFalha.value) : null;
    salvarRascunhoAgora();
  });

  // ---- Ajuda: Tipo de Manutencao (EFD-010-A) -----------------------------

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

  // ---- Campos simples restantes: OS, N. SA, Data -------------------------

  const campoNumeroOs = document.getElementById('campo-numero-os');
  const campoNumeroSa = document.getElementById('campo-numero-sa');
  const campoData = document.getElementById('campo-data');

  campoNumeroOs.value = rascunho.numero_os || '';
  campoNumeroSa.value = rascunho.numero_sa || '';
  campoData.value = rascunho.data_preenchimento || '';

  campoNumeroOs.addEventListener('input', function () {
    rascunho.numero_os = campoNumeroOs.value ? Number(campoNumeroOs.value) : null;
    salvarRascunhoAgora();
  });
  campoNumeroSa.addEventListener('input', function () {
    // Somente digitos, ate 10 caracteres (VLD-028) -- filtra na digitacao.
    campoNumeroSa.value = campoNumeroSa.value.replace(/\D/g, '').slice(0, 10);
    rascunho.numero_sa = campoNumeroSa.value;
    salvarRascunhoAgora();
  });
  campoData.addEventListener('change', function () {
    rascunho.data_preenchimento = campoData.value;
    salvarRascunhoAgora();
  });

  // Primeiro salvamento (garante que sync_id_tentativa e os defaults,
  // como equipes: ['VP'], ja fiquem gravados mesmo sem o usuario alterar nada).
  await salvarRascunhoAgora();

  // ---- Horarios (Bloco 2) -------------------------------------------------
  //
  // RG-HOR-001 a 027. Usa RegrasHorario (regras_horario.js), o mesmo
  // calculo do backend (rad/regras_horario.py), para dar feedback
  // imediato offline. O calculo definitivo e sempre refeito no
  // servidor na sincronizacao -- aqui e so para o usuario ver.

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

  const grupoAtrasoInicio = document.getElementById('campo-grupo-atraso-inicio');
  const grupoAtrasoTermino = document.getElementById('campo-grupo-atraso-termino');
  const selectMotivoInicio = document.getElementById('campo-motivo-atraso-inicio');
  const selectMotivoTermino = document.getElementById('campo-motivo-atraso-termino');
  const grupoDescInicio = document.getElementById('campo-grupo-desc-atraso-inicio');
  const grupoDescTermino = document.getElementById('campo-grupo-desc-atraso-termino');
  const campoDescInicio = document.getElementById('campo-desc-atraso-inicio');
  const campoDescTermino = document.getElementById('campo-desc-atraso-termino');

  // Datas HP/HR Inicio nao podem ser futuras.
  const hojeIso = new Date().toISOString().slice(0, 10);
  campoDataHpInicio.max = hojeIso;
  campoDataHrInicio.max = hojeIso;

  [
    ['id_motivo_atraso_inicio', selectMotivoInicio],
    ['id_motivo_atraso_termino', selectMotivoTermino],
  ].forEach(function ([_chave, selectEl]) {
    const opcaoVazia = document.createElement('option');
    opcaoVazia.value = '';
    opcaoVazia.textContent = 'Selecione…';
    selectEl.appendChild(opcaoVazia);
    motivosAtraso.forEach(function (motivo) {
      const opcao = document.createElement('option');
      opcao.value = motivo.id;
      opcao.textContent = motivo.nome;
      selectEl.appendChild(opcao);
    });
  });

  function nomeDoMotivo(lista, id) {
    const motivo = lista.find((m) => String(m.id) === String(id));
    return motivo ? motivo.nome : '';
  }

  // Rastreia se o usuario ja editou manualmente a data de termino --
  // nesse caso a virada de meia-noite automatica para de sobrescrever
  // (RG-HOR-022: "usuario podera editar a data resultante").
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
    // --- Virada de meia-noite (HP) ---
    if (rascunho.hora_prog_inicio && rascunho.hora_prog_termino && !dataHpTerminoEditadaManualmente) {
      const novaData = RegrasHorario.ajustarDataPorViradaDeMeiaNoite(
        campoDataHpInicio.value, rascunho.hora_prog_inicio, rascunho.hora_prog_termino
      );
      campoDataHpTermino.value = novaData;
      rascunho.data_hp_termino = novaData;
    }
    // --- Virada de meia-noite (HR) ---
    if (rascunho.hora_real_inicio && rascunho.hora_real_termino && !dataHrTerminoEditadaManualmente) {
      const novaData = RegrasHorario.ajustarDataPorViradaDeMeiaNoite(
        campoDataHrInicio.value, rascunho.hora_real_inicio, rascunho.hora_real_termino
      );
      campoDataHrTermino.value = novaData;
      rascunho.data_hr_termino = novaData;
    }

    // --- Duracoes ---
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

    // --- Atrasos (RG-HOR-006/007/019: ocultos quando Tipo = Falha) ---
    const ocultarAtrasos = tipoManutencaoEhFalha();
    let atrasoInicio = false;
    let atrasoTermino = false;

    if (!ocultarAtrasos && dtProgInicio && dtRealInicio) {
      atrasoInicio = RegrasHorario.calcularAtrasoInicio(dtProgInicio, dtRealInicio);
    }
    if (!ocultarAtrasos && dtProgTermino && dtRealTermino) {
      atrasoTermino = RegrasHorario.calcularAtrasoTermino(dtProgTermino, dtRealTermino);
    }

    grupoAtrasoInicio.style.display = atrasoInicio ? '' : 'none';
    grupoAtrasoTermino.style.display = atrasoTermino ? '' : 'none';

    if (!atrasoInicio) {
      rascunho.id_motivo_atraso_inicio = null;
      rascunho.desc_motivo_atraso_inicio = '';
      selectMotivoInicio.value = '';
      campoDescInicio.value = '';
      grupoDescInicio.style.display = 'none';
    }
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

  selectMotivoInicio.addEventListener('change', function () {
    rascunho.id_motivo_atraso_inicio = selectMotivoInicio.value ? Number(selectMotivoInicio.value) : null;
    const ehOutros = nomeDoMotivo(motivosAtraso, selectMotivoInicio.value) === 'Outros';
    grupoDescInicio.style.display = ehOutros ? '' : 'none';
    if (!ehOutros) {
      rascunho.desc_motivo_atraso_inicio = '';
      campoDescInicio.value = '';
    }
    salvarRascunhoAgora();
  });
  campoDescInicio.addEventListener('input', function () {
    rascunho.desc_motivo_atraso_inicio = campoDescInicio.value;
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

  // Tipo de Manutencao ja tinha um listener (Bloco 1); a troca tambem
  // precisa recalcular a visibilidade dos atrasos (RG-HOR-006/007/019).
  campoTipoManutencao.addEventListener('change', recalcularHorarios);

  // ---- Servicos Executados + Bloco AMV (Bloco 3) ---------------------------
  //
  // RG-EXE-001 a 005 (servicos, "Outros"), EFD-020-B/C (bloco AMV).
  //
  // Nota de implementacao: a EFD descreve Modelo/Via/Local da MCH como
  // editaveis pelo usuario, mas o backend atual (rad/regras_negocio.py)
  // sempre grava os valores vindos do cadastro da MCH, ignorando
  // qualquer edicao -- entao aqui esses campos sao exibidos como
  // somente-leitura, para nao sugerir uma edicao que seria descartada
  // silenciosamente na sincronizacao. Se o backend ganhar suporte a
  // edicao desses campos, esta tela pode virar campos editaveis.

  const servicos = await RadDB.obterCatalogo('servicos');
  const mchs = await RadDB.obterCatalogo('mch');
  const tiposDefeitoAmv = await RadDB.obterCatalogo('tipos_defeito_amv');
  const acoesAmv = await RadDB.obterCatalogo('acoes_amv');

  const listaServicosEl = document.getElementById('lista-servicos');
  const grupoOutrosServico = document.getElementById('campo-grupo-outros-servico');
  const campoOutrosServicoDesc = document.getElementById('campo-outros-servico-desc');
  const blocoAmv = document.getElementById('bloco-amv');

  function renderizarListaCheckbox(containerEl, itens, valoresSelecionados, aoMudar, comAjuda) {
    containerEl.innerHTML = '';
    itens.forEach(function (item) {
      const linha = document.createElement('label');
      linha.style.display = 'flex';
      linha.style.alignItems = 'flex-start';
      linha.style.gap = '0.5rem';
      linha.style.fontWeight = '400';

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

      if (comAjuda && item.ajuda) {
        const detalhes = document.createElement('details');
        detalhes.style.marginLeft = '1.75rem';
        detalhes.style.fontSize = '0.8rem';
        detalhes.style.color = 'var(--cor-tinta-suave)';
        const resumo = document.createElement('summary');
        resumo.textContent = 'O que é isso?';
        resumo.style.cursor = 'pointer';
        detalhes.appendChild(resumo);
        const paragrafo = document.createElement('p');
        paragrafo.textContent = item.ajuda;
        detalhes.appendChild(paragrafo);
        const envolucro = document.createElement('div');
        envolucro.appendChild(linha);
        envolucro.appendChild(detalhes);
        containerEl.appendChild(envolucro);
      } else {
        containerEl.appendChild(linha);
      }
    });
  }

  function servicoRequerAmvSelecionado() {
    return servicos.some((s) => s.requer_amv && rascunho.servicos.includes(s.id));
  }
  function servicoOutrosSelecionado() {
    return servicos.some((s) => s.requer_descricao && rascunho.servicos.includes(s.id));
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

  /**
   * Redesenha o conteudo do bloco AMV a partir de rascunho.amv. As
   * arrays tipos_defeito/acoes de rascunho.amv NUNCA sao substituidas
   * (sempre mutadas in-place via push/splice) -- assim os checkboxes
   * renderizados aqui continuam validos mesmo depois do bloco ser
   * escondido e mostrado de novo.
   */
  function renderizarBlocoAmv() {
    campoMch.value = rascunho.amv.id_mch ? (mchs.find((m) => m.id === rascunho.amv.id_mch) || {}).identificacao || '' : '';
    preencherDetalhesMch(rascunho.amv.id_mch);

    renderizarListaCheckbox(
      document.getElementById('lista-tipos-defeito'),
      tiposDefeitoAmv.map((t) => ({ valor: t.id, rotulo: t.nome })),
      rascunho.amv.tipos_defeito,
      salvarRascunhoAgora
    );
    renderizarListaCheckbox(
      document.getElementById('lista-acoes-amv'),
      acoesAmv.map((a) => ({ valor: a.id, rotulo: a.nome })),
      rascunho.amv.acoes,
      salvarRascunhoAgora
    );
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
      // Limpa em memoria (mesmas referencias de array, so esvaziadas)
      // ao desmarcar o servico de AMV.
      rascunho.amv.id_mch = null;
      rascunho.amv.tipos_defeito.length = 0;
      rascunho.amv.acoes.length = 0;
      campoMch.value = '';
      detalhesMch.style.display = 'none';
    }
  }

  renderizarListaCheckbox(
    listaServicosEl,
    servicos.map((s) => ({ valor: s.id, rotulo: s.nome, ajuda: s.descricao })),
    rascunho.servicos,
    function () {
      atualizarVisibilidadeServicos();
      salvarRascunhoAgora();
    },
    true
  );
  atualizarVisibilidadeServicos();

  campoOutrosServicoDesc.value = rascunho.outros_servico_desc || '';
  campoOutrosServicoDesc.addEventListener('input', function () {
    rascunho.outros_servico_desc = campoOutrosServicoDesc.value;
    salvarRascunhoAgora();
  });

  campoMch.addEventListener('change', function () {
    const idMch = mapaMchPorRotulo.get(campoMch.value.trim());
    rascunho.amv.id_mch = idMch || null;
    preencherDetalhesMch(idMch);
    salvarRascunhoAgora();
  });

  // ---- Colaboradores e Participantes (Bloco 4) -----------------------------
  //
  // RG-RESP-001 a 015. A busca funciona offline: colaboradores_cadastro
  // e cacheado no IndexedDB (ver db.js::atualizarCatalogos) e filtrado
  // aqui no cliente, em vez de bater em /colaboradores/buscar/ a cada
  // tecla -- assim o técnico consegue adicionar colaboradores em campo,
  // sem sinal.

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
        // RG-RESP-007: remocao livre antes da sincronizacao.
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
    // RG-RESP-009: mesmo registro nao pode ser adicionado duas vezes.
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
      // RG-RESP-008
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
          nome: candidato.nome, // RG-RESP-004/005: nome nunca editavel manualmente
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

  // ---- Anexos (Bloco 5) -----------------------------------------------------
  //
  // RG-ANX-001 a 011. Fotos/PDF ficam guardados como File/Blob direto
  // no rascunho -- IndexedDB clona objetos File nativamente (structured
  // clone), entao nao precisa de nenhuma conversao especial para
  // persistir localmente junto com o resto do rascunho.

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
      inputEl.value = ''; // permite selecionar o mesmo arquivo de novo depois
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

  // ---- Campos finais (Bloco 6): Responsavel, Operador CCM, Descricao ----
  // ---- Tecnica, Materiais Utilizados, Observacoes Gerais -----------------
  //
  // Campos de texto livre, sem logica condicional. VLD-029
  // (responsavel_atividade obrigatorio, 50 caracteres) e VLD-030
  // (operador_ccm, 25 caracteres) sao reforcados aqui so como limite de
  // digitacao -- a obrigatoriedade de verdade e conferida no backend na
  // sincronizacao (Bloco 7), que e a fonte definitiva de validacao.

  function ligarCampoTexto(elementoId, chaveRascunho) {
    const elemento = document.getElementById(elementoId);
    elemento.value = rascunho[chaveRascunho] || '';
    elemento.addEventListener('input', function () {
      rascunho[chaveRascunho] = elemento.value;
      salvarRascunhoAgora();
    });
  }

  ligarCampoTexto('campo-responsavel-atividade', 'responsavel_atividade');
  ligarCampoTexto('campo-operador-ccm', 'operador_ccm');
  ligarCampoTexto('campo-descricao-tecnica', 'descricao_tecnica_atividade');
  ligarCampoTexto('campo-materiais-utilizados', 'materiais_utilizados');
  ligarCampoTexto('campo-observacoes-gerais', 'observacoes_gerais');

  // ---- Sincronizar (Bloco 7) -------------------------------------------
  //
  // RG-SYNC-001 a 027. O botao Sincronizar e o unico jeito de enviar o
  // RAD ao servidor -- tudo antes disso e so rascunho local. As
  // validacoes de obrigatoriedade so rodam aqui (RG-SYNC-017); o
  // servidor e quem decide de verdade se o RAD pode ser criado.

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
      // RG-SYNC-006/026: visivel, porem desabilitado sem conexao.
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
  atualizarEstadoBotaoExportar(); // caso o rascunho carregado ja tenha tudo preenchido

  // ---- Exportar (RG-EXP-001 a 010) ---------------------------------------
  //
  // 100% offline: nao faz nenhuma chamada de rede. PDF via jsPDF
  // (hospedado localmente, ver vendor/jspdf.umd.min.js), "Word" via
  // HTML servido com extensao .doc (o Word abre nativamente), mensagem
  // via texto puro -- tudo montado a partir do rascunho local +
  // catalogos ja cacheados no IndexedDB.

  const modalExportar = document.getElementById('modal-exportar');
  const avisoExportarRascunho = document.getElementById('aviso-exportar-rascunho');

  document.getElementById('botao-exportar').addEventListener('click', function () {
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

  document.getElementById('botao-exportar-mensagem').addEventListener('click', async function () {
    try {
      const mensagem = ExportarCliente.gerarMensagemCopiar(rascunho, catalogosParaExportar());
      await navigator.clipboard.writeText(mensagem);
      avisoExportarRascunho.innerHTML = '<div class="aviso aviso--sucesso">Mensagem copiada para a área de transferência.</div>';
      modalExportar.style.display = 'none';
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
    // Mesmas chaves que rad/regras_negocio.py::processar_sincronizacao
    // espera (ver teste de contrato em interface/tests.py). Os arquivos
    // (rascunho.anexos.*) NAO entram aqui -- vao direto no FormData,
    // fora do JSON.
    return {
      numero_os: rascunho.numero_os,
      numero_sa: rascunho.numero_sa,
      data_preenchimento: rascunho.data_preenchimento,
      id_local_inicial: rascunho.id_local_inicial,
      id_local_final: rascunho.id_local_final,
      linhas: rascunho.linhas,
      vias: rascunho.vias,
      equipes: rascunho.equipes,
      km_poste: rascunho.km_poste,
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
      id_motivo_atraso_inicio: rascunho.id_motivo_atraso_inicio,
      desc_motivo_atraso_inicio: rascunho.desc_motivo_atraso_inicio,
      id_motivo_atraso_termino: rascunho.id_motivo_atraso_termino,
      desc_motivo_atraso_termino: rascunho.desc_motivo_atraso_termino,
      servicos: rascunho.servicos,
      outros_servico_desc: rascunho.outros_servico_desc,
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
        // RG-SYNC-008/021: sincronizado -- o rascunho local e removido,
        // o RAD passa a existir so no servidor.
        await RadDB.limparRascunho(sessao.login);
        avisoSincronizacao.innerHTML =
          '<div class="aviso aviso--sucesso">RAD sincronizado com sucesso!</div>';
        setTimeout(function () {
          window.location.href = '/inicio/';
        }, 1200);
        return;
      }

      if (resposta.status === 422) {
        // RG-SYNC-012/017: validacao falhou -- volta para Rascunho
        // Local, nada e perdido, usuario corrige e tenta de novo.
        const corpo = await resposta.json();
        renderizarErrosSincronizacao(corpo.erros || []);
      } else {
        const corpo = await resposta.json().catch(() => ({}));
        renderizarErrosSincronizacao([
          { mensagem: corpo.erro || 'Erro inesperado ao sincronizar. Tente novamente.' },
        ]);
      }
    } catch (erro) {
      // RG-SYNC-012: falha de rede -- volta para Rascunho Local.
      renderizarErrosSincronizacao([
        { mensagem: 'Erro de conexão durante a sincronização. Seus dados continuam salvos neste dispositivo — tente novamente.' },
      ]);
    } finally {
      sincronizando = false;
      atualizarEstadoBotaoSincronizar();
    }
  });

});
