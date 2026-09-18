/*
 * Logica do formulario de preenchimento do RAD.
 */
document.addEventListener('DOMContentLoaded', async function () {
  if (!RadAuth.exigirSessao()) return;

  const sessao = RadAuth.obterSessao();
  document.getElementById('conteudo-protegido').style.display = '';

  const statusRascunho = document.getElementById('status-rascunho');
  const avisoFormulario = document.getElementById('aviso-formulario');

  // 26/08/2026 (achado de auditoria de seguranca -- XSS armazenado):
  // nome de colaborador (cadastro, pode vir de importacao CSV feita
  // por um Administrador) e detalhes de MCH (catalogo) sao inseridos
  // no HTML deste formulario -- sem escapar, um nome ou valor de
  // catalogo malicioso rodaria como codigo na tela de QUALQUER pessoa
  // que buscasse esse colaborador/MCH em qualquer RAD novo. Mesmo
  // padrao de correcao ja aplicado em detalhe_rad.html e
  // gerenciar_usuarios.js.
  function escapar(texto) {
    const div = document.createElement('div');
    div.textContent = texto ?? '';
    return div.innerHTML;
  }

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
  // 15/09/2026: "Anomalias Observadas" foi redesenhada -- de um bloco
  // fixo (com uma lista separada so pra Dimensoes) para uma lista de
  // "Itens" repetiveis, cada um com seu proprio conjunto completo de
  // campos, incluindo Dimensoes (agora um conjunto FIXO de 7 campos
  // por item, nao mais uma lista aninhada). Um rascunho salvo ANTES
  // desta mudanca tem os campos antigos soltos (canaleta_anomalias,
  // canaleta_grau_criticidade etc.) -- migra pra um unico Item, se
  // havia algo preenchido. As Dimensoes antigas (formato incompativel
  // com os 7 campos novos) NAO dao pra migrar automatico sem inventar
  // valor -- o item migrado comeca com Dimensoes vazias, a pessoa
  // reconfirma se precisar.
  if (!rascunho.canaleta_itens) {
    const tinhaAlgumaCoisaAntiga = !!(
      rascunho.canaleta_grau_criticidade ||
      (rascunho.canaleta_anomalias && rascunho.canaleta_anomalias.length) ||
      (rascunho.canaleta_lados && rascunho.canaleta_lados.length)
    );
    rascunho.canaleta_itens = tinhaAlgumaCoisaAntiga
      ? [{
          anomalias: rascunho.canaleta_anomalias || [],
          grau_criticidade: rascunho.canaleta_grau_criticidade || '',
          justificativa: rascunho.canaleta_justificativa || '',
          necessita_cautela: rascunho.canaleta_necessita_cautela || '',
          lados: rascunho.canaleta_lados || [],
          dimensao: {
            largura_inicial: '', largura_inicial_nao_identificado: false,
            largura_final: '', largura_final_nao_identificado: false,
            altura_inicial: '', altura_inicial_nao_identificado: false,
            altura_final: '', altura_final_nao_identificado: false,
            comprimento: '', comprimento_nao_identificado: false,
            km_poste_inicial: '', km_poste_inicial_nao_identificado: false,
            km_poste_final: '', km_poste_final_nao_identificado: false,
          },
        }]
      : [];
  }
  delete rascunho.canaleta_anomalias;
  delete rascunho.canaleta_grau_criticidade;
  delete rascunho.canaleta_justificativa;
  delete rascunho.canaleta_necessita_cautela;
  delete rascunho.canaleta_lados;
  delete rascunho.canaleta_dimensoes;
  delete rascunho.canaleta_largura_inicial;
  delete rascunho.canaleta_largura_final;
  delete rascunho.canaleta_altura_inicial;
  delete rascunho.canaleta_altura_final;
  delete rascunho.canaleta_comprimento;

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
      // 05/09/2026: Data da Atividade -- ao contrario dos demais
      // campos de data, nasce VAZIA de proposito (decisao do
      // cliente confirmada) -- obriga a pessoa a preencher, em vez
      // de vir com hoje pre-selecionado como todo o resto do
      // formulario.
      data_atividade: '',
      id_local_inicial: '',
      id_local_final: '',
      linhas: [],
      vias: [],
      equipes: ['VP'],
      // 14/09/2026: Km/Poste virou dois campos (Inicial e Final) --
      // ver aplicarMascaraKmPosteNova mais abaixo. 17/09/2026: padrao
      // mudou de "XXX/XXX + XXX" para "XX/XX + XXX".
      km_poste_inicial: '',
      km_poste_final: '',
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
      // 15/09/2026: "Anomalias Observadas" -- lista de Itens, vazia
      // por padrao (bloco inteiro e opcional).
      canaleta_itens: [],
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

  // 14/09/2026: Km/Poste virou dois campos (Inicial e Final).
  // 17/09/2026: padrao mudou de "XXX/XXX + XXX" para "XX/XX + XXX"
  // (2 digitos / 2 digitos + 3 digitos), mesmas regras de antes --
  // so o tamanho dos dois primeiros grupos diminuiu. Funcao de
  // mascara PROPRIA, separada de aplicarMascaraKmPoste (mais abaixo)
  // -- aquela continua com o padrao antigo "XX/XX - XX/XX", ainda
  // usado pelas linhas antigas de Dimensoes (RadCanaletaDimensao,
  // descontinuada para RADs novos).
  function aplicarMascaraKmPosteNova(valorDigitado) {
    const digitos = valorDigitado.replace(/\D/g, '').slice(0, 7);
    let resultado = digitos;
    if (digitos.length > 2) resultado = digitos.slice(0, 2) + '/' + digitos.slice(2);
    if (digitos.length > 4) resultado = resultado.slice(0, 5) + ' + ' + digitos.slice(4);
    return resultado;
  }

  function configurarCampoKmPoste(inputEl, chaveRascunho) {
    inputEl.value = rascunho[chaveRascunho] || '';
    inputEl.addEventListener('input', function () {
      inputEl.value = aplicarMascaraKmPosteNova(inputEl.value);
      rascunho[chaveRascunho] = inputEl.value;
      salvarRascunhoAgora();
    });
  }

  configurarCampoKmPoste(document.getElementById('campo-km-poste-inicial'), 'km_poste_inicial');
  configurarCampoKmPoste(document.getElementById('campo-km-poste-final'), 'km_poste_final');

  function aplicarMascaraKmPoste(valorDigitado) {
    const digitos = valorDigitado.replace(/\D/g, '').slice(0, 8);
    let resultado = digitos;
    if (digitos.length > 2) resultado = digitos.slice(0, 2) + '/' + digitos.slice(2);
    if (digitos.length > 4) resultado = resultado.slice(0, 5) + ' - ' + digitos.slice(4);
    if (digitos.length > 6) resultado = resultado.slice(0, 10) + '/' + digitos.slice(6);
    return resultado;
  }

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
  // 14/09/2026: Data de Preenchimento deixou de ser editavel -- sempre
  // mostra e grava a data de HOJE, recalculada toda vez que a tela
  // abre (mesmo que o rascunho seja de um dia anterior). Sem
  // addEventListener('change', ...) porque o campo esta desabilitado
  // no HTML -- nao ha interacao do usuario pra escutar.
  const dataDeHojeParaPreenchimento = new Date().toISOString().slice(0, 10);
  campoData.value = dataDeHojeParaPreenchimento;
  rascunho.data_preenchimento = dataDeHojeParaPreenchimento;

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

  // 05/09/2026: Data da Atividade -- campo de texto com mascara
  // DD/MM/AAAA (digita so numeros) + um calendario ao lado (input
  // nativo type=date, posicionado por cima do icone via CSS -- ver
  // novo_rad.html). Guardamos rascunho.data_atividade sempre em ISO
  // (AAAA-MM-DD), igual todo outro campo de data do formulario que
  // ja vai pro backend -- as duas funcoes abaixo so convertem entre
  // o formato de exibicao (BR) e o de armazenamento (ISO).
  function aplicarMascaraData(valorDigitado) {
    const digitos = valorDigitado.replace(/\D/g, '').slice(0, 8);
    let resultado = digitos;
    if (digitos.length > 2) resultado = digitos.slice(0, 2) + '/' + digitos.slice(2);
    if (digitos.length > 4) resultado = resultado.slice(0, 5) + '/' + digitos.slice(4);
    return resultado;
  }

  function dataBrParaIso(dataBr) {
    const partes = dataBr.split('/');
    if (partes.length !== 3 || partes[2].length !== 4) return '';
    const [dia, mes, ano] = partes;
    return `${ano}-${mes}-${dia}`;
  }

  function dataIsoParaBr(dataIso) {
    if (!dataIso) return '';
    const [ano, mes, dia] = dataIso.split('-');
    return `${dia}/${mes}/${ano}`;
  }

  const campoDataAtividade = document.getElementById('campo-data-atividade');
  const campoDataAtividadePicker = document.getElementById('campo-data-atividade-picker');

  campoDataAtividade.value = dataIsoParaBr(rascunho.data_atividade);

  campoDataAtividade.addEventListener('input', function () {
    campoDataAtividade.value = aplicarMascaraData(campoDataAtividade.value);
    const iso = dataBrParaIso(campoDataAtividade.value);
    rascunho.data_atividade = iso;
    if (iso) campoDataAtividadePicker.value = iso;
    salvarRascunhoAgora();
  });

  campoDataAtividadePicker.addEventListener('change', function () {
    rascunho.data_atividade = campoDataAtividadePicker.value;
    campoDataAtividade.value = dataIsoParaBr(campoDataAtividadePicker.value);
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
      if (itensDoGrupo.length === 0) return;

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
  function servicoRequerCanaletaSelecionado() {
    return algumServicoSelecionadoTem('requer_canaleta');
  }

  function servicoInfraSelecionado() {
    return servicos.some((s) => s.area === 'infra' && rascunho.servicos.includes(s.id));
  }

  function limiteFotoAtual(categoria) {
    const area = servicoInfraSelecionado() ? 'infra' : 'padrao';
    const item = limitesFotos.find((l) => l.categoria === categoria && l.area === area);
    return item ? item.limite : ValidadoresArquivos.LIMITE_FOTOS_POR_CATEGORIA;
  }

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

  const MAXIMO_BLOCOS_AMV = 16;
  const containerBlocosAmv = document.getElementById('container-blocos-amv');
  const botaoAdicionarMch = document.getElementById('botao-adicionar-mch');
  const contadorBlocosAmv = document.getElementById('contador-blocos-amv');

  function criarBlocoAmvVazio() {
    return {
      id_mch: null, tipos_defeito: [], acoes: [], desc_outros_tipo_defeito: '', desc_outros_acao: '',
      mch_nao_cadastrada: false, desc_mch_nao_cadastrada: '',
    };
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

    const campoMchGrupo = document.createElement('div');
    campoMchGrupo.className = 'campo';
    campoMchGrupo.innerHTML = `<label>Identificação MCH</label>`;
    const inputMch = document.createElement('input');
    inputMch.type = 'text';
    inputMch.autocomplete = 'off';
    inputMch.placeholder = 'Buscar MCH…';
    const mchAtual = mchs.find((m) => m.id === bloco.id_mch);
    inputMch.value = mchAtual ? mchAtual.identificacao : '';
    campoMchGrupo.appendChild(inputMch);

    // 04/09/2026: padronizado com o mesmo padrao de busca usado em
    // Local Inicial/Final e Colaborador -- lista de resultados
    // clicaveis abaixo do campo, em vez do <datalist> nativo do
    // navegador (que tinha aparencia/comportamento diferente do resto
    // do formulario).
    const resultadosMchEl = document.createElement('div');
    resultadosMchEl.className = 'pilha';
    resultadosMchEl.style.marginTop = '0.5rem';
    campoMchGrupo.appendChild(resultadosMchEl);

    const detalhesMchEl = document.createElement('div');
    detalhesMchEl.className = 'bloco-amv__detalhes-mch';

    function atualizarDetalhesMch() {
      if (!bloco.id_mch) {
        detalhesMchEl.style.display = 'none';
        return;
      }
      const detalhes = montarDetalhesMchTexto(bloco.id_mch);
      // 26/08/2026 (achado de auditoria -- XSS armazenado): valores de
      // MCH vem do catalogo (CatMch), controlado pelo Administrador --
      // escapar() aqui e defesa em profundidade, caso uma importacao
      // de catalogo acabe trazendo algo inesperado.
      detalhesMchEl.innerHTML = `
        <div><span class="texto-suave" style="font-size:0.8rem;">Modelo</span><br><strong>${escapar(detalhes.modelo)}</strong></div>
        <div><span class="texto-suave" style="font-size:0.8rem;">Via</span><br><strong>${escapar(detalhes.via)}</strong></div>
        <div><span class="texto-suave" style="font-size:0.8rem;">UR</span><br><strong>${escapar(detalhes.ur)}</strong></div>
        <div><span class="texto-suave" style="font-size:0.8rem;">Local</span><br><strong>${escapar(detalhes.local)}</strong></div>
        <div><span class="texto-suave" style="font-size:0.8rem;">Linha</span><br><strong>${escapar(detalhes.linha)}</strong></div>
      `;
      detalhesMchEl.style.display = 'flex';
    }
    atualizarDetalhesMch();
    campoMchGrupo.appendChild(detalhesMchEl);

    // 04/09/2026: checkbox "MCH não cadastrada" -- via alternativa
    // para quando a MCH verificada em campo ainda nao existe no
    // catalogo. Quando marcado, desabilita a busca de MCH (que fica
    // sem sentido nesse caso) e libera um campo de texto livre (ate
    // 50 caracteres) que passa a ser obrigatorio no lugar dela -- ver
    // rad/validadores.py::_validar_bloco_amv. As duas exigencias
    // (MCH do catalogo OU descricao) nunca coexistem no mesmo bloco.
    const grupoMchNaoCadastrada = document.createElement('div');
    grupoMchNaoCadastrada.style.marginTop = '0.6rem';

    const labelMchNaoCadastrada = document.createElement('label');
    labelMchNaoCadastrada.style.display = 'flex';
    labelMchNaoCadastrada.style.alignItems = 'center';
    labelMchNaoCadastrada.style.gap = '0.4rem';
    labelMchNaoCadastrada.style.cursor = 'pointer';
    labelMchNaoCadastrada.style.minHeight = 'var(--alvo-toque)';

    const checkboxMchNaoCadastrada = document.createElement('input');
    checkboxMchNaoCadastrada.type = 'checkbox';
    checkboxMchNaoCadastrada.checked = !!bloco.mch_nao_cadastrada;
    labelMchNaoCadastrada.appendChild(checkboxMchNaoCadastrada);
    labelMchNaoCadastrada.appendChild(document.createTextNode('MCH não cadastrada'));
    grupoMchNaoCadastrada.appendChild(labelMchNaoCadastrada);

    const grupoDescMchNaoCadastrada = document.createElement('div');
    grupoDescMchNaoCadastrada.style.marginTop = '0.5rem';
    grupoDescMchNaoCadastrada.innerHTML = '<label>Descreva a MCH</label>';
    const campoDescMchNaoCadastrada = document.createElement('input');
    campoDescMchNaoCadastrada.type = 'text';
    campoDescMchNaoCadastrada.maxLength = 50;
    campoDescMchNaoCadastrada.value = bloco.desc_mch_nao_cadastrada || '';
    campoDescMchNaoCadastrada.addEventListener('input', function () {
      bloco.desc_mch_nao_cadastrada = campoDescMchNaoCadastrada.value;
      salvarRascunhoAgora();
    });
    grupoDescMchNaoCadastrada.appendChild(campoDescMchNaoCadastrada);
    grupoMchNaoCadastrada.appendChild(grupoDescMchNaoCadastrada);

    function atualizarEstadoMchNaoCadastrada() {
      const marcado = checkboxMchNaoCadastrada.checked;
      inputMch.disabled = marcado;
      grupoDescMchNaoCadastrada.style.display = marcado ? '' : 'none';
      if (marcado) {
        bloco.id_mch = null;
        inputMch.value = '';
        detalhesMchEl.style.display = 'none';
      } else {
        bloco.desc_mch_nao_cadastrada = '';
        campoDescMchNaoCadastrada.value = '';
        atualizarDetalhesMch();
      }
    }

    checkboxMchNaoCadastrada.addEventListener('change', function () {
      bloco.mch_nao_cadastrada = checkboxMchNaoCadastrada.checked;
      atualizarEstadoMchNaoCadastrada();
      salvarRascunhoAgora();
    });

    campoMchGrupo.appendChild(grupoMchNaoCadastrada);
    atualizarEstadoMchNaoCadastrada();

    function selecionarMch(mch) {
      inputMch.value = mch.identificacao;
      bloco.id_mch = mch.id;
      resultadosMchEl.innerHTML = '';
      atualizarDetalhesMch();
      salvarRascunhoAgora();
    }

    inputMch.addEventListener('input', function () {
      const termo = inputMch.value.trim().toLowerCase();
      resultadosMchEl.innerHTML = '';
      bloco.id_mch = null;
      atualizarDetalhesMch();

      if (!termo) return;

      const encontradas = mchs
        .filter((m) => m.identificacao.toLowerCase().includes(termo))
        .slice(0, 8);

      if (encontradas.length === 0) {
        const aviso = document.createElement('p');
        aviso.className = 'texto-suave';
        aviso.style.fontSize = '0.85rem';
        aviso.textContent = 'Nenhuma MCH encontrada.';
        resultadosMchEl.appendChild(aviso);
        return;
      }

      encontradas.forEach(function (mch) {
        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'botao botao--secundaria';
        botao.style.textAlign = 'left';
        botao.style.justifyContent = 'flex-start';
        botao.textContent = mch.identificacao;
        botao.addEventListener('click', function () {
          selecionarMch(mch);
        });
        resultadosMchEl.appendChild(botao);
      });
    });

    inputMch.addEventListener('blur', function () {
      setTimeout(function () {
        resultadosMchEl.innerHTML = '';
      }, 150);
    });
    cartao.appendChild(campoMchGrupo);

    const grupoDefeito = document.createElement('div');
    grupoDefeito.className = 'campo';
    grupoDefeito.innerHTML = '<label>Tipo de Defeito</label>';
    const listaDefeitoEl = document.createElement('div');
    listaDefeitoEl.className = 'grade-checkboxes';
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

    const grupoAcoes = document.createElement('div');
    grupoAcoes.className = 'campo';
    grupoAcoes.innerHTML = '<label>Ações</label>';
    const listaAcoesEl = document.createElement('div');
    listaAcoesEl.className = 'grade-checkboxes';
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

  const blocoCanaleta = document.getElementById('bloco-canaleta');
  const containerItensCanaleta = document.getElementById('container-itens-canaleta');
  const botaoAdicionarItemCanaleta = document.getElementById('botao-adicionar-item-canaleta');
  const contadorItensCanaleta = document.getElementById('contador-itens-canaleta');

  const ANOMALIAS_CANALETA = [
    { valor: 'limpa', rotulo: 'Limpa' },
    { valor: 'obstruida', rotulo: 'Obstruída' },
    { valor: 'ausente', rotulo: 'Ausente' },
    { valor: 'quebrada', rotulo: 'Quebrada' },
  ];
  // 17/09/2026: adicionada "Esgoto" como tipo de obstrução, junto das
  // demais (Vegetação, Lastro, Lixo, Dormentes, Entulho, Terra) -- ver
  // tambem rad/validadores.py (ANOMALIAS_CANALETA_VALIDAS e
  // SUB_ANOMALIAS_OBSTRUIDA_CANALETA) e rad/models.py
  // (RadCanaletaAnomalia.ANOMALIA_CHOICES), que precisam do mesmo
  // valor 'esgoto' para aceitar/exibir corretamente.
  const SUB_ANOMALIAS_OBSTRUIDA_CANALETA = [
    { valor: 'vegetacao', rotulo: 'Vegetação' },
    { valor: 'lastro', rotulo: 'Lastro' },
    { valor: 'lixo', rotulo: 'Lixo' },
    { valor: 'dormentes', rotulo: 'Dormentes' },
    { valor: 'entulho', rotulo: 'Entulho' },
    { valor: 'terra', rotulo: 'Terra' },
    { valor: 'esgoto', rotulo: 'Esgoto' },
  ];
  const LADOS_CANALETA = [
    { valor: 'direito', rotulo: 'Direito' },
    { valor: 'esquerdo', rotulo: 'Esquerdo' },
    { valor: 'entrevia', rotulo: 'Entrevia' },
  ];
  const MAXIMO_ITENS_CANALETA = 15;
  const ROTULOS_GRAU_CRITICIDADE = { baixa: 'Baixa', media: 'Média', alta: 'Alta', critica: 'Crítica' };
  // 15/09/2026: Dimensoes agora e um conjunto FIXO de 7 campos por
  // Item (nao mais uma lista de linhas) -- cada um com seu proprio
  // checkbox "Não identificado". Km/Poste Inicial/Final usam a MESMA
  // mascara nova do Km/Poste de Localizacao (aplicarMascaraKmPosteNova).
  // 17/09/2026: padrao mudou de "XXX/XXX + XXX" para "XX/XX + XXX".
  const CAMPOS_DIMENSAO_ITEM_CANALETA = [
    ['largura_inicial', 'Largura Inicial (m)', 'numero'],
    ['largura_final', 'Largura Final (m)', 'numero'],
    ['altura_inicial', 'Altura Inicial (m)', 'numero'],
    ['altura_final', 'Altura Final (m)', 'numero'],
    ['comprimento', 'Comprimento (m)', 'numero'],
    ['km_poste_inicial', 'Km/Poste Inicial', 'km'],
    ['km_poste_final', 'Km/Poste Final', 'km'],
  ];

  function criarItemCanaletaVazio() {
    return {
      anomalias: [],
      grau_criticidade: '',
      justificativa: '',
      necessita_cautela: '',
      lados: [],
      dimensao: {
        largura_inicial: '', largura_inicial_nao_identificado: false,
        largura_final: '', largura_final_nao_identificado: false,
        altura_inicial: '', altura_inicial_nao_identificado: false,
        altura_final: '', altura_final_nao_identificado: false,
        comprimento: '', comprimento_nao_identificado: false,
        km_poste_inicial: '', km_poste_inicial_nao_identificado: false,
        km_poste_final: '', km_poste_final_nao_identificado: false,
      },
    };
  }

  function renderizarItemCanaletaIndividual(item, indice) {
    const cartao = document.createElement('div');
    cartao.className = 'cartao item-canaleta';

    const cabecalho = document.createElement('div');
    cabecalho.className = 'item-canaleta__cabecalho';
    const titulo = document.createElement('p');
    titulo.className = 'item-canaleta__titulo';
    titulo.textContent = `Item ${indice + 1} de ${rascunho.canaleta_itens.length}`;
    cabecalho.appendChild(titulo);

    const botaoRemover = document.createElement('button');
    botaoRemover.type = 'button';
    botaoRemover.className = 'botao botao--perigo';
    botaoRemover.style.width = 'auto';
    botaoRemover.style.minHeight = '32px';
    botaoRemover.style.padding = '0 0.8rem';
    botaoRemover.style.fontSize = '0.8rem';
    botaoRemover.textContent = 'Remover';
    botaoRemover.addEventListener('click', function () {
      rascunho.canaleta_itens.splice(indice, 1);
      renderizarItensCanaleta();
      salvarRascunhoAgora();
    });
    cabecalho.appendChild(botaoRemover);
    cartao.appendChild(cabecalho);

    // 1) Dimensões -- sem botao de adicionar linha, conjunto fixo de
    // 7 campos, cada um com seu proprio checkbox "Não identificado".
    const secaoDimensao = document.createElement('div');
    secaoDimensao.className = 'item-canaleta__secao';
    const tituloDimensao = document.createElement('p');
    tituloDimensao.className = 'item-canaleta__secao-titulo';
    tituloDimensao.textContent = 'Dimensões';
    secaoDimensao.appendChild(tituloDimensao);

    const gradeDimensao = document.createElement('div');
    gradeDimensao.className = 'grade-campos--dimensao-canaleta';

    CAMPOS_DIMENSAO_ITEM_CANALETA.forEach(function ([chave, rotulo, tipo]) {
      const campoDiv = document.createElement('div');
      campoDiv.className = 'campo';
      const label = document.createElement('label');
      label.className = 'texto-suave';
      label.style.fontSize = '0.75rem';
      label.textContent = rotulo;
      campoDiv.appendChild(label);

      const input = document.createElement('input');
      if (tipo === 'numero') {
        input.type = 'number';
        input.step = '0.01';
        input.min = '0';
      } else {
        input.type = 'text';
        input.inputMode = 'numeric';
        input.placeholder = 'XX/XX + XXX';
        input.maxLength = 11;
      }
      input.value = item.dimensao[chave];
      input.disabled = !!item.dimensao[`${chave}_nao_identificado`];
      input.addEventListener('input', function () {
        if (tipo === 'km') {
          input.value = aplicarMascaraKmPosteNova(input.value);
        }
        item.dimensao[chave] = input.value;
        salvarRascunhoAgora();
      });
      campoDiv.appendChild(input);

      const labelCheckbox = document.createElement('label');
      labelCheckbox.className = 'campo-dimensao-item__nao-identificado';
      const checkboxNaoIdentificado = document.createElement('input');
      checkboxNaoIdentificado.type = 'checkbox';
      checkboxNaoIdentificado.checked = !!item.dimensao[`${chave}_nao_identificado`];
      checkboxNaoIdentificado.addEventListener('change', function () {
        item.dimensao[`${chave}_nao_identificado`] = checkboxNaoIdentificado.checked;
        input.disabled = checkboxNaoIdentificado.checked;
        if (checkboxNaoIdentificado.checked) {
          input.value = '';
          item.dimensao[chave] = '';
        }
        salvarRascunhoAgora();
      });
      labelCheckbox.appendChild(checkboxNaoIdentificado);
      labelCheckbox.appendChild(document.createTextNode('Não identificado'));
      campoDiv.appendChild(labelCheckbox);

      gradeDimensao.appendChild(campoDiv);
    });
    secaoDimensao.appendChild(gradeDimensao);
    cartao.appendChild(secaoDimensao);

    // 2) Grau de Criticidade
    const secaoCriticidade = document.createElement('div');
    secaoCriticidade.className = 'item-canaleta__secao campo';
    secaoCriticidade.innerHTML = '<label>Grau de Criticidade</label>';
    const selectCriticidade = document.createElement('select');
    [['', 'Selecione…'], ['baixa', 'Baixa'], ['media', 'Média'], ['alta', 'Alta'], ['critica', 'Crítica']].forEach(
      function ([valor, rotuloOpcao]) {
        const opcao = document.createElement('option');
        opcao.value = valor;
        opcao.textContent = rotuloOpcao;
        selectCriticidade.appendChild(opcao);
      }
    );
    selectCriticidade.value = item.grau_criticidade || '';
    selectCriticidade.addEventListener('change', function () {
      item.grau_criticidade = selectCriticidade.value;
      salvarRascunhoAgora();
    });
    secaoCriticidade.appendChild(selectCriticidade);
    cartao.appendChild(secaoCriticidade);

    // 3) Anomalias
    const secaoAnomalias = document.createElement('div');
    secaoAnomalias.className = 'item-canaleta__secao campo';
    secaoAnomalias.innerHTML = '<label>Anomalias</label>';
    const listaAnomaliasEl = document.createElement('div');
    listaAnomaliasEl.className = 'grade-checkboxes';
    secaoAnomalias.appendChild(listaAnomaliasEl);

    const grupoObstrucao = document.createElement('div');
    grupoObstrucao.style.display = 'none';
    grupoObstrucao.style.marginTop = '0.6rem';
    grupoObstrucao.innerHTML = '<label class="texto-suave" style="font-size:0.85rem;">Tipo de obstrução</label>';
    const listaSubAnomaliasEl = document.createElement('div');
    listaSubAnomaliasEl.className = 'grade-checkboxes grade-checkboxes--sub';
    grupoObstrucao.appendChild(listaSubAnomaliasEl);
    secaoAnomalias.appendChild(grupoObstrucao);

    function atualizarVisibilidadeSubAnomalias() {
      const obstruidaMarcada = item.anomalias.includes('obstruida');
      grupoObstrucao.style.display = obstruidaMarcada ? '' : 'none';
      if (!obstruidaMarcada) {
        let mudou = false;
        SUB_ANOMALIAS_OBSTRUIDA_CANALETA.forEach(function (sub) {
          const idx = item.anomalias.indexOf(sub.valor);
          if (idx !== -1) {
            item.anomalias.splice(idx, 1);
            mudou = true;
          }
        });
        if (mudou) {
          renderizarListaCheckbox(listaSubAnomaliasEl, SUB_ANOMALIAS_OBSTRUIDA_CANALETA, item.anomalias, aoMudarAnomalia);
        }
      }
    }
    function aoMudarAnomalia() {
      atualizarVisibilidadeSubAnomalias();
      salvarRascunhoAgora();
    }
    renderizarListaCheckbox(listaAnomaliasEl, ANOMALIAS_CANALETA, item.anomalias, aoMudarAnomalia);
    renderizarListaCheckbox(listaSubAnomaliasEl, SUB_ANOMALIAS_OBSTRUIDA_CANALETA, item.anomalias, aoMudarAnomalia);
    atualizarVisibilidadeSubAnomalias();
    cartao.appendChild(secaoAnomalias);

    // 4) Justificativa -- 15/09/2026: sempre visivel, sempre opcional
    // (deixou de ser obrigatoria em qualquer grau de criticidade).
    const secaoJustificativa = document.createElement('div');
    secaoJustificativa.className = 'item-canaleta__secao campo';
    secaoJustificativa.innerHTML = '<label>Justificativa <span class="texto-suave" style="font-size:0.78rem; font-weight:400;">(opcional)</span></label>';
    const textareaJustificativa = document.createElement('textarea');
    textareaJustificativa.value = item.justificativa || '';
    textareaJustificativa.addEventListener('input', function () {
      item.justificativa = textareaJustificativa.value;
      salvarRascunhoAgora();
    });
    secaoJustificativa.appendChild(textareaJustificativa);
    cartao.appendChild(secaoJustificativa);

    // 5) Necessita de Cautela?
    const secaoCautela = document.createElement('div');
    secaoCautela.className = 'item-canaleta__secao campo';
    secaoCautela.innerHTML = '<label>Necessita de Cautela?</label>';
    const selectCautela = document.createElement('select');
    [['', 'Selecione…'], ['sim', 'Sim'], ['nao', 'Não']].forEach(function ([valor, rotuloOpcao]) {
      const opcao = document.createElement('option');
      opcao.value = valor;
      opcao.textContent = rotuloOpcao;
      selectCautela.appendChild(opcao);
    });
    selectCautela.value = item.necessita_cautela || '';
    selectCautela.addEventListener('change', function () {
      item.necessita_cautela = selectCautela.value;
      salvarRascunhoAgora();
    });
    secaoCautela.appendChild(selectCautela);
    cartao.appendChild(secaoCautela);

    // 6) Lado
    const secaoLado = document.createElement('div');
    secaoLado.className = 'item-canaleta__secao campo';
    secaoLado.innerHTML = '<label>Lado</label>';
    const listaLadoEl = document.createElement('div');
    listaLadoEl.className = 'grade-checkboxes';
    renderizarListaCheckbox(listaLadoEl, LADOS_CANALETA, item.lados, salvarRascunhoAgora);
    secaoLado.appendChild(listaLadoEl);
    cartao.appendChild(secaoLado);

    return cartao;
  }

  function renderizarItensCanaleta() {
    containerItensCanaleta.innerHTML = '';
    rascunho.canaleta_itens.forEach(function (item, indice) {
      containerItensCanaleta.appendChild(renderizarItemCanaletaIndividual(item, indice));
    });
    contadorItensCanaleta.textContent = rascunho.canaleta_itens.length > 0
      ? `${rascunho.canaleta_itens.length} de ${MAXIMO_ITENS_CANALETA} itens usados`
      : '';
    botaoAdicionarItemCanaleta.style.display =
      rascunho.canaleta_itens.length >= MAXIMO_ITENS_CANALETA ? 'none' : '';
  }

  botaoAdicionarItemCanaleta.addEventListener('click', function () {
    if (rascunho.canaleta_itens.length >= MAXIMO_ITENS_CANALETA) return;
    rascunho.canaleta_itens.push(criarItemCanaletaVazio());
    renderizarItensCanaleta();
    salvarRascunhoAgora();
  });

  const blocoTerceiros = document.getElementById('bloco-terceiros');
  const campoGrupoTerceirosOpMaquina = document.getElementById('campo-grupo-terceiros-op-maquina');
  const campoGrupoTerceirosVolume = document.getElementById('campo-grupo-terceiros-volume');

  function limparCampoTerceiros(elementoId, chaveRascunho) {
    document.getElementById(elementoId).value = '';
    rascunho[chaveRascunho] = '';
  }

  // 15/09/2026: "Anomalias Observadas" e opcional mesmo com o servico
  // selecionado -- limpar so esvazia a lista de Itens, sem forcar
  // nenhum item vazio de volta.
  function limparBlocoCanaleta() {
    rascunho.canaleta_itens.length = 0;
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

    if (servicoRequerCanaletaSelecionado()) {
      blocoCanaleta.style.display = '';
      renderizarItensCanaleta();
    } else {
      blocoCanaleta.style.display = 'none';
      limparBlocoCanaleta();
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
      const registro = pessoa.registro_empresa ? ` · Registro ${escapar(pessoa.registro_empresa)}` : '';
      // 26/08/2026 (achado de auditoria -- XSS armazenado): nome de
      // colaborador vem do cadastro (pode ter sido importado via CSV
      // por um Administrador) -- sem escapar, um nome malicioso
      // afetaria qualquer pessoa que buscasse esse colaborador em
      // qualquer RAD novo daqui pra frente.
      linha.innerHTML = `
        <div>
          <strong>${escapar(pessoa.nome)}</strong>
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

  const ROTULOS_COMENTARIO_FOTO = {
    desc_foto_1: 'Foto 1',
    desc_foto_2: 'Foto 2',
    desc_foto_3: 'Foto 3',
    desc_foto_4: 'Foto 4',
  };
  const botoesComentariosFotos = document.getElementById('botoes-comentarios-fotos');
  const camposComentariosFotos = document.getElementById('campos-comentarios-fotos');
  const rotuloComentariosObrigatorio = document.getElementById('rotulo-comentarios-fotos-obrigatorio');

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
      if (obrigatorio) chip.disabled = true;
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

  // 15/09/2026: virou um unico botao -- Sincronizar sempre tenta
  // enviar ao Drive em seguida, automaticamente (nao e mais uma
  // escolha separada). O id do elemento ficou como
  // 'botao-sincronizar-drive' (reaproveitado do que antes era o
  // segundo botao) pra nao precisar tocar no HTML de novo.
  const botaoSincronizar = document.getElementById('botao-sincronizar-drive');
  const textoStatusBotao = document.getElementById('texto-status-botao');
  const avisoSincronizacao = document.getElementById('aviso-sincronizacao');
  const listaErrosSincronizacao = document.getElementById('lista-erros-sincronizacao');

  function atualizarEstadoBotaoSincronizar() {
    if (sincronizando) {
      botaoSincronizar.disabled = true;
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
      data_atividade: rascunho.data_atividade,
      id_local_inicial: rascunho.id_local_inicial,
      id_local_final: rascunho.id_local_final,
      linhas: rascunho.linhas,
      vias: rascunho.vias,
      equipes: rascunho.equipes,
      km_poste_inicial: rascunho.km_poste_inicial,
      km_poste_final: rascunho.km_poste_final,
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
      // 15/09/2026: "Anomalias Observadas" -- lista de Itens, sempre
      // enviada (mesmo vazia, ja que o bloco e opcional). Cada item
      // manda o par valor+"_nao_identificado" pra cada um dos 7
      // campos de Dimensao -- o backend usa esse par pra decidir se
      // aceita vazio ou exige numero/texto.
      canaleta_itens: (rascunho.canaleta_itens || []).map(function (item) {
        return {
          anomalias: item.anomalias,
          grau_criticidade: item.grau_criticidade || null,
          justificativa: item.justificativa || null,
          necessita_cautela:
            item.necessita_cautela === 'sim' ? true :
            (item.necessita_cautela === 'nao' ? false : null),
          lados: item.lados,
          dimensao: {
            largura_inicial: item.dimensao.largura_inicial !== '' ? Number(item.dimensao.largura_inicial) : null,
            largura_inicial_nao_identificado: !!item.dimensao.largura_inicial_nao_identificado,
            largura_final: item.dimensao.largura_final !== '' ? Number(item.dimensao.largura_final) : null,
            largura_final_nao_identificado: !!item.dimensao.largura_final_nao_identificado,
            altura_inicial: item.dimensao.altura_inicial !== '' ? Number(item.dimensao.altura_inicial) : null,
            altura_inicial_nao_identificado: !!item.dimensao.altura_inicial_nao_identificado,
            altura_final: item.dimensao.altura_final !== '' ? Number(item.dimensao.altura_final) : null,
            altura_final_nao_identificado: !!item.dimensao.altura_final_nao_identificado,
            comprimento: item.dimensao.comprimento !== '' ? Number(item.dimensao.comprimento) : null,
            comprimento_nao_identificado: !!item.dimensao.comprimento_nao_identificado,
            km_poste_inicial: item.dimensao.km_poste_inicial || null,
            km_poste_inicial_nao_identificado: !!item.dimensao.km_poste_inicial_nao_identificado,
            km_poste_final: item.dimensao.km_poste_final || null,
            km_poste_final_nao_identificado: !!item.dimensao.km_poste_final_nao_identificado,
          },
        };
      }),
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
      .map((e) => `<li>${escapar(e.mensagem || e.campo)}</li>`)
      .join('');
    listaErrosSincronizacao.innerHTML = `
      <div class="aviso aviso--erro">
        <strong>Não foi possível sincronizar. Corrija os itens abaixo:</strong>
        <ul style="margin: 0.5rem 0 0; padding-left: 1.2rem;">${itens}</ul>
      </div>
    `;
    listaErrosSincronizacao.scrollIntoView && listaErrosSincronizacao.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // 15/09/2026: reaproveitada pelos dois botoes -- Sincronizar e
  // Sincronizar e Salvar no Drive. tambemSalvarNoDrive so muda o que
  // acontece DEPOIS que a sincronizacao normal ja deu certo -- o RAD
  // so pode ser salvo no Drive depois de existir de verdade no banco
  // (com numero_rad definido), entao essa chamada vem sempre em
  // seguida da sincronizacao, nunca no lugar dela.
  async function executarSincronizacao(tambemSalvarNoDrive) {
    if (sincronizando || !navigator.onLine) return;

    sincronizando = true;
    atualizarEstadoBotaoSincronizar();
    botaoSincronizar.textContent = 'Sincronizando…';
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
        const corpo = await resposta.json();
        await RadDB.limparRascunho(sessao.login);

        if (!tambemSalvarNoDrive) {
          avisoSincronizacao.innerHTML =
            '<div class="aviso aviso--sucesso">RAD sincronizado com sucesso!</div>';
          setTimeout(function () {
            window.location.href = '/inicio/';
          }, 1200);
          return;
        }

        avisoSincronizacao.innerHTML =
          '<div class="aviso aviso--sucesso">RAD sincronizado! Salvando no Google Drive…</div>';
        try {
          const respostaDrive = await RadAuth.requisicaoAutenticada(
            `/consulta/rads/${encodeURIComponent(corpo.numero_rad)}/docx-drive/`
          );
          const corpoDrive = await respostaDrive.json().catch(function () { return {}; });
          if (respostaDrive.ok) {
            avisoSincronizacao.innerHTML =
              '<div class="aviso aviso--sucesso">RAD sincronizado e salvo no Google Drive!</div>';
            window.open(corpoDrive.link, '_blank');
          } else {
            // 15/09/2026: o RAD ja sincronizou com sucesso nesse ponto
            // -- uma falha so no upload pro Drive nao pode passar a
            // impressao de que o RAD inteiro falhou. Aviso de atencao,
            // nao de erro, deixando claro que so a parte do Drive nao
            // deu certo.
            avisoSincronizacao.innerHTML =
              `<div class="aviso aviso--atencao">RAD sincronizado com sucesso, mas não foi possível salvar no Drive: ${corpoDrive.erro || 'erro desconhecido'}.</div>`;
          }
        } catch (erroDrive) {
          avisoSincronizacao.innerHTML =
            '<div class="aviso aviso--atencao">RAD sincronizado com sucesso, mas houve erro de conexão ao salvar no Drive.</div>';
        }
        setTimeout(function () {
          window.location.href = '/inicio/';
        }, 2500);
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
  }

  botaoSincronizar.addEventListener('click', function () {
    executarSincronizacao(true);
  });

});
