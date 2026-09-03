/*
 * Dashboard -- paineis agregados sobre RADs sincronizados (28/08/2026,
 * ampliado 03/09/2026). Acesso: Supervisor e Administrador. Abre
 * sozinho com os ultimos 30 dias; qualquer outro ajuste de filtro so
 * recalcula ao clicar em "Pesquisar" (mesmo padrao usado no resto do
 * sistema).
 */
document.addEventListener('DOMContentLoaded', async function () {
  if (!RadAuth.exigirSessao()) return;
  if (!RadAuth.temPerfil('supervisor', 'administrador')) {
    window.location.href = '/inicio/';
    return;
  }
  document.getElementById('conteudo-protegido').style.display = '';

  const souAdministrador = RadAuth.temPerfil('administrador');
  if (souAdministrador) {
    document.getElementById('botao-exportar-excel').style.display = '';
  }

  const avisoDashboard = document.getElementById('aviso-dashboard');

  function escapar(texto) {
    const div = document.createElement('div');
    div.textContent = texto ?? '';
    return div.innerHTML;
  }

  function mostrarAviso(mensagem, tipo) {
    avisoDashboard.innerHTML = `<div class="aviso aviso--${tipo}">${escapar(mensagem)}</div>`;
  }

  function limparAviso() {
    avisoDashboard.innerHTML = '';
  }

  // ---------------------------------------------------------------
  // Catálogos: popula Linha, Via, Tipo de Manutenção e a árvore de
  // Serviço executado (Área + Subcategoria). Também guarda o ID do
  // serviço "Inspeção de Canaleta" -- usado para decidir se mostra o
  // painel de Canaleta por criticidade (03/09/2026).
  // ---------------------------------------------------------------
  const ROTULO_AREA = {
    geral: 'Geral', infra: 'Infra', corretiva: 'Corretiva',
    mecanizada: 'Mecanizada', amv: 'AMV', outros: 'Outros',
  };
  const ORDEM_AREAS = ['geral', 'infra', 'corretiva', 'mecanizada', 'amv', 'outros'];

  let locais = [];
  let servicosPorArea = {};
  let idServicoInspecaoCanaleta = null;

  function popularSelect(id, itens, valorChave, rotuloFn) {
    const select = document.getElementById(id);
    itens.forEach(function (item) {
      const opcao = document.createElement('option');
      opcao.value = item[valorChave];
      opcao.textContent = rotuloFn(item);
      select.appendChild(opcao);
    });
  }

  function popularAreasServico() {
    const container = document.getElementById('lista-areas-servico');
    let html = '';
    ORDEM_AREAS.forEach(function (area) {
      if (area !== 'outros' && !servicosPorArea[area]) return;
      html += `<label>
        <input type="checkbox" class="checkbox-area-servico" value="${area}"> ${ROTULO_AREA[area]}
      </label>`;
    });
    container.innerHTML = html;

    container.querySelectorAll('.checkbox-area-servico').forEach(function (checkbox) {
      checkbox.addEventListener('change', atualizarSubcategoria);
    });
  }

  function atualizarSubcategoria() {
    const areasMarcadas = Array.from(
      document.querySelectorAll('.checkbox-area-servico:checked')
    ).map((el) => el.value).filter((area) => area !== 'outros');

    const campoSubcategoria = document.getElementById('campo-subcategoria-servico');
    const listaSubcategoria = document.getElementById('lista-subcategoria-servico');

    const areasParaMostrar = areasMarcadas.length > 0 ? areasMarcadas : Object.keys(servicosPorArea);

    if (areasParaMostrar.length === 0) {
      campoSubcategoria.style.display = 'none';
      listaSubcategoria.innerHTML = '';
      return;
    }

    let html = '';
    areasParaMostrar.forEach(function (area) {
      (servicosPorArea[area] || []).forEach(function (servico) {
        html += `<label>
          <input type="checkbox" class="checkbox-subcategoria-servico" value="${servico.id}"> ${escapar(servico.nome)}
        </label>`;
      });
    });
    listaSubcategoria.innerHTML = html;
    campoSubcategoria.style.display = '';
  }

  async function carregarCatalogos() {
    try {
      const resposta = await RadAuth.requisicaoAutenticada('/catalogos/todos/');
      if (!resposta.ok) {
        console.error('Falha ao buscar /catalogos/todos/:', resposta.status);
        mostrarAviso('Não foi possível carregar os catálogos dos filtros.', 'erro');
        return;
      }
      const catalogos = await resposta.json();

      locais = catalogos.locais;

      popularSelect('filtro-linha', catalogos.linhas, 'codigo', (l) => `${l.codigo} - ${l.nome}`);
      popularSelect('filtro-via', catalogos.vias, 'id', (v) => v.nome);
      popularSelect('filtro-tipo-manutencao', catalogos.tipos_manutencao, 'id', (t) => t.nome);

      servicosPorArea = {};
      catalogos.servicos.forEach(function (servico) {
        if (servico.nome === 'Outros') return;
        if (!servicosPorArea[servico.area]) servicosPorArea[servico.area] = [];
        servicosPorArea[servico.area].push(servico);
      });
      popularAreasServico();
      atualizarSubcategoria();

      const servicoCanaleta = catalogos.servicos.find((s) => s.nome === 'Inspeção de Canaleta');
      idServicoInspecaoCanaleta = servicoCanaleta ? String(servicoCanaleta.id) : null;
    } catch (erro) {
      console.error('Erro ao carregar catalogos do dashboard:', erro);
      mostrarAviso('Erro ao carregar os catálogos dos filtros. Veja o console (F12) para detalhes.', 'erro');
    }
  }

  // ---------------------------------------------------------------
  // Busca "Pessoa que preencheu"
  // ---------------------------------------------------------------
  async function configurarBuscaPessoa() {
    const campoBusca = document.getElementById('filtro-pessoa-busca');
    const campoValor = document.getElementById('filtro-pessoa-login');
    const resultadosEl = document.getElementById('resultados-pessoa');

    let colaboradores = [];
    try {
      const resposta = await RadAuth.requisicaoAutenticada('/colaboradores/todos/');
      if (resposta.ok) {
        const dados = await resposta.json();
        colaboradores = dados.colaboradores;
      }
    } catch (erro) {
      return;
    }

    campoBusca.addEventListener('input', function () {
      const termo = campoBusca.value.trim().toLowerCase();
      resultadosEl.innerHTML = '';
      campoValor.value = '';
      if (!termo) return;

      const encontrados = colaboradores
        .filter((c) => c.registro_empresa.toLowerCase().includes(termo) || c.nome.toLowerCase().includes(termo))
        .slice(0, 8);

      encontrados.forEach(function (colaborador) {
        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'botao botao--secundaria';
        botao.style.textAlign = 'left';
        botao.style.justifyContent = 'flex-start';
        botao.textContent = `${colaborador.registro_empresa} — ${colaborador.nome}`;
        botao.addEventListener('click', function () {
          campoBusca.value = `${colaborador.registro_empresa} — ${colaborador.nome}`;
          campoValor.value = colaborador.registro_empresa;
          resultadosEl.innerHTML = '';
        });
        resultadosEl.appendChild(botao);
      });
    });

    campoBusca.addEventListener('blur', function () {
      setTimeout(function () { resultadosEl.innerHTML = ''; }, 150);
    });
  }

  // ---------------------------------------------------------------
  // Busca "Local" (combinado -- inicial ou final)
  // ---------------------------------------------------------------
  function configurarBuscaLocal() {
    const campoBusca = document.getElementById('filtro-local-busca');
    const campoValor = document.getElementById('filtro-local-sigla');
    const resultadosEl = document.getElementById('resultados-local');

    campoBusca.addEventListener('input', function () {
      const termo = campoBusca.value.trim().toLowerCase();
      resultadosEl.innerHTML = '';
      campoValor.value = '';
      if (!termo) return;

      const encontrados = locais
        .filter((l) => l.sigla.toLowerCase().includes(termo) || l.nome.toLowerCase().includes(termo))
        .slice(0, 8);

      encontrados.forEach(function (local) {
        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'botao botao--secundaria';
        botao.style.textAlign = 'left';
        botao.style.justifyContent = 'flex-start';
        botao.textContent = `${local.sigla} — ${local.nome}`;
        botao.addEventListener('click', function () {
          campoBusca.value = `${local.sigla} — ${local.nome}`;
          campoValor.value = local.sigla;
          resultadosEl.innerHTML = '';
        });
        resultadosEl.appendChild(botao);
      });
    });

    campoBusca.addEventListener('blur', function () {
      setTimeout(function () { resultadosEl.innerHTML = ''; }, 150);
    });
  }

  // ---------------------------------------------------------------
  // Parâmetros de filtro
  // ---------------------------------------------------------------
  function montarParametrosFiltro() {
    const parametros = new URLSearchParams();

    function definirSeExistir(idCampo, nomeParametro) {
      const valor = document.getElementById(idCampo).value.trim();
      if (valor) parametros.set(nomeParametro, valor);
    }

    definirSeExistir('filtro-data-de', 'data_de');
    definirSeExistir('filtro-data-ate', 'data_ate');
    definirSeExistir('filtro-pessoa-login', 'login_usuario');
    definirSeExistir('filtro-linha', 'linha');
    definirSeExistir('filtro-via', 'via');
    definirSeExistir('filtro-local-sigla', 'local');
    definirSeExistir('filtro-tipo-manutencao', 'id_tipo_manutencao');

    const areasMarcadas = Array.from(document.querySelectorAll('.checkbox-area-servico:checked')).map((el) => el.value);
    const areasReais = areasMarcadas.filter((a) => a !== 'outros');
    if (areasReais.length > 0) parametros.set('servico_areas', areasReais.join(','));
    if (areasMarcadas.includes('outros')) parametros.set('servico_outros', '1');

    const idsMarcados = Array.from(document.querySelectorAll('.checkbox-subcategoria-servico:checked')).map((el) => el.value);
    if (idsMarcados.length > 0) parametros.set('servico_ids', idsMarcados.join(','));

    return parametros;
  }

  // ---------------------------------------------------------------
  // Gráfico de linha "RADs por dia" -- com número acima de cada
  // ponto, grade horizontal (eixo Y) e vertical (uma por dia) e
  // rótulo de data embaixo de cada dia (03/09/2026).
  // ---------------------------------------------------------------
  function renderizarGraficoLinha(radsPorDia, dataDe, dataAte) {
    const container = document.getElementById('grafico-rads-por-dia');

    const mapa = {};
    radsPorDia.forEach(function (item) { mapa[item.data] = item.total; });

    const dias = [];
    if (dataDe && dataAte) {
      let cursor = new Date(dataDe + 'T00:00:00');
      const fim = new Date(dataAte + 'T00:00:00');
      while (cursor <= fim) {
        const iso = cursor.toISOString().slice(0, 10);
        dias.push({ data: iso, total: mapa[iso] || 0 });
        cursor.setDate(cursor.getDate() + 1);
      }
    } else {
      Object.keys(mapa).sort().forEach(function (data) {
        dias.push({ data: data, total: mapa[data] });
      });
    }

    if (dias.length === 0) {
      container.innerHTML = '<p class="texto-suave" style="font-size:0.85rem;">Sem dados no período.</p>';
      return;
    }

    const pxPorDia = 44;
    const margemEsquerda = 30;
    const margemInferior = 46;
    const margemSuperior = 22;
    const alturaUtil = 90;
    const altura = margemSuperior + alturaUtil + margemInferior;
    const largura = margemEsquerda + dias.length * pxPorDia + 10;

    const maximo = Math.max(...dias.map((d) => d.total), 1);

    function escalaY(valor) {
      return margemSuperior + alturaUtil - (valor / maximo) * alturaUtil;
    }

    const pontos = dias.map(function (d, indice) {
      return {
        x: margemEsquerda + indice * pxPorDia + pxPorDia / 2,
        y: escalaY(d.total),
        total: d.total,
        data: d.data,
      };
    });

    const linhaPontos = pontos.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

    const ticksY = maximo >= 2 ? [0, Math.round(maximo / 2), maximo] : [0, maximo];
    const gridHorizontal = ticksY.map(function (valor) {
      const y = escalaY(valor);
      return `
        <line x1="${margemEsquerda}" y1="${y.toFixed(1)}" x2="${largura - 5}" y2="${y.toFixed(1)}" stroke="var(--cor-linha)" stroke-width="1"/>
        <text x="0" y="${(y + 3).toFixed(1)}" font-size="9" fill="var(--cor-tinta-suave)">${valor}</text>
      `;
    }).join('');

    const gridVertical = pontos.map(function (p) {
      const dataFormatada = p.data.split('-').slice(1).reverse().join('/'); // dd/mm
      return `
        <line x1="${p.x}" y1="${margemSuperior}" x2="${p.x}" y2="${margemSuperior + alturaUtil}" stroke="var(--cor-linha)" stroke-width="0.5" stroke-dasharray="2,2"/>
        <text x="${p.x}" y="${(p.y - 8).toFixed(1)}" font-size="9" fill="var(--cor-tinta)" text-anchor="middle" font-weight="700">${p.total}</text>
        <circle cx="${p.x}" cy="${p.y.toFixed(1)}" r="2.5" fill="var(--cor-primaria)"/>
        <text x="${p.x}" y="${(margemSuperior + alturaUtil + 14).toFixed(1)}" font-size="8.5" fill="var(--cor-tinta-suave)" text-anchor="end" transform="rotate(-45 ${p.x} ${(margemSuperior + alturaUtil + 14).toFixed(1)})">${dataFormatada}</text>
      `;
    }).join('');

    container.innerHTML = `
      <svg viewBox="0 0 ${largura} ${altura}" style="width:${largura}px; height:${altura}px; max-width:none; display:block;">
        ${gridHorizontal}
        ${gridVertical}
        <polyline points="${linhaPontos}" fill="none" stroke="var(--cor-primaria)" stroke-width="2"/>
      </svg>
    `;
  }

  // ---------------------------------------------------------------
  // Listas em barra horizontal (reaproveitada por RADs por área, Top
  // locais, Top usuários, Top MCH e Canaleta por criticidade)
  // ---------------------------------------------------------------
  function renderizarListaBarras(idContainer, itens, rotuloFn) {
    const container = document.getElementById(idContainer);
    if (!itens || itens.length === 0) {
      container.innerHTML = '<p class="texto-suave" style="font-size:0.85rem;">Sem dados no período.</p>';
      return;
    }
    const maximo = Math.max(...itens.map((i) => i.total), 1);
    container.innerHTML = itens.map(function (item) {
      const rotulo = rotuloFn(item);
      const percentual = Math.round((item.total / maximo) * 100);
      return `
        <div class="barra-horizontal">
          <span class="barra-horizontal__rotulo" title="${escapar(rotulo)}">${escapar(rotulo)}</span>
          <div class="barra-horizontal__trilha">
            <div class="barra-horizontal__preenchimento" style="width:${percentual}%;"></div>
          </div>
          <span class="barra-horizontal__valor">${item.total}</span>
        </div>
      `;
    }).join('');
  }

  const ROTULO_AREA_GRAFICO = {
    geral: 'Geral', infra: 'Infra', corretiva: 'Corretiva', mecanizada: 'Mecanizada', amv: 'AMV',
  };

  function renderizarTabelaMotivos(motivos) {
    const tbody = document.getElementById('tabela-motivos-atraso');
    if (!motivos || motivos.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="texto-suave" style="text-align:center;">Sem atrasos no período.</td></tr>';
      return;
    }
    tbody.innerHTML = motivos.map(function (item) {
      const descricao = item.descricoes ? escapar(item.descricoes) : '—';
      return `<tr><td>${escapar(item.motivo)}</td><td>${item.total}</td><td class="coluna-descricao" title="${descricao}">${descricao}</td></tr>`;
    }).join('');
  }

  // ---------------------------------------------------------------
  // Card "Atraso no término" -- alterna entre % e Nº absoluto
  // (03/09/2026).
  // ---------------------------------------------------------------
  let mostrarAtrasoComoNumero = false;
  let ultimoResultado = null;

  function atualizarCardAtraso() {
    if (!ultimoResultado) return;
    const valorEl = document.getElementById('metrica-atraso-termino');
    valorEl.textContent = mostrarAtrasoComoNumero
      ? ultimoResultado.total_atraso_termino
      : `${ultimoResultado.percentual_atraso_termino}%`;
  }

  document.getElementById('botao-alternar-atraso').addEventListener('click', function () {
    mostrarAtrasoComoNumero = !mostrarAtrasoComoNumero;
    this.textContent = mostrarAtrasoComoNumero ? 'Ver %' : 'Ver Nº';
    atualizarCardAtraso();
  });

  // ---------------------------------------------------------------
  // Pesquisar
  // ---------------------------------------------------------------
  async function pesquisar() {
    limparAviso();
    const botao = document.getElementById('botao-pesquisar');
    botao.disabled = true;
    botao.textContent = 'Pesquisando…';

    try {
      const parametros = montarParametrosFiltro();
      const resposta = await RadAuth.requisicaoAutenticada(`/dashboard/dados/?${parametros.toString()}`);
      if (!resposta.ok) {
        mostrarAviso('Não foi possível carregar os dados do dashboard.', 'erro');
        return;
      }
      const dados = await resposta.json();
      ultimoResultado = dados;

      document.getElementById('metrica-total-rads').textContent = dados.total_rads;
      atualizarCardAtraso();

      const dataDe = document.getElementById('filtro-data-de').value;
      const dataAte = document.getElementById('filtro-data-ate').value;
      renderizarGraficoLinha(dados.rads_por_dia, dataDe, dataAte);

      renderizarListaBarras('grafico-rads-por-area', dados.rads_por_area, (i) => ROTULO_AREA_GRAFICO[i.area] || i.area);
      renderizarTabelaMotivos(dados.motivos_atraso);
      renderizarListaBarras('grafico-top-locais', dados.top_locais, (i) => `${i.sigla} - ${i.nome}`);
      renderizarListaBarras('grafico-top-usuarios', dados.top_usuarios, (i) => i.nome);
      renderizarListaBarras('grafico-top-mch', dados.top_mch_defeito, (i) => i.mch);

      // Painel de Canaleta por criticidade so aparece quando o
      // servico especifico "Inspeção de Canaleta" esta marcado no
      // filtro de Subcategoria (decisao do cliente).
      const idsMicroMarcados = Array.from(
        document.querySelectorAll('.checkbox-subcategoria-servico:checked')
      ).map((el) => el.value);
      const mostrarCanaleta = idServicoInspecaoCanaleta && idsMicroMarcados.includes(idServicoInspecaoCanaleta);
      document.getElementById('cartao-canaleta-criticidade').style.display = mostrarCanaleta ? '' : 'none';
      if (mostrarCanaleta) {
        renderizarListaBarras('grafico-canaleta-criticidade', dados.canaleta_por_criticidade, (i) => i.rotulo);
      }
    } catch (erro) {
      console.error('Erro ao pesquisar dashboard:', erro);
      mostrarAviso('Erro de conexão ao carregar o dashboard.', 'erro');
    } finally {
      botao.disabled = false;
      botao.textContent = 'Pesquisar';
    }
  }

  document.getElementById('botao-pesquisar').addEventListener('click', pesquisar);

  document.getElementById('botao-limpar-filtros').addEventListener('click', function () {
    document.getElementById('filtro-pessoa-busca').value = '';
    document.getElementById('filtro-pessoa-login').value = '';
    document.getElementById('resultados-pessoa').innerHTML = '';
    document.getElementById('filtro-linha').value = '';
    document.getElementById('filtro-via').value = '';
    document.getElementById('filtro-local-busca').value = '';
    document.getElementById('filtro-local-sigla').value = '';
    document.getElementById('resultados-local').innerHTML = '';
    document.getElementById('filtro-tipo-manutencao').value = '';
    document.querySelectorAll('.checkbox-area-servico:checked, .checkbox-subcategoria-servico:checked')
      .forEach((el) => { el.checked = false; });
    atualizarSubcategoria();
    definirPeriodoPadrao();
  });

  // ---------------------------------------------------------------
  // Exportar Excel (Administrador)
  // ---------------------------------------------------------------
  if (souAdministrador) {
    document.getElementById('botao-exportar-excel').addEventListener('click', async function () {
      limparAviso();
      const botao = document.getElementById('botao-exportar-excel');
      botao.disabled = true;
      const textoOriginal = botao.textContent;
      botao.textContent = 'Exportando…';

      try {
        const parametros = montarParametrosFiltro();
        const resposta = await RadAuth.requisicaoAutenticada(`/dashboard/exportar-excel/?${parametros.toString()}`);

        if (!resposta.ok) {
          const corpo = await resposta.json().catch(function () { return {}; });
          mostrarAviso(corpo.erro || 'Não foi possível gerar a exportação.', 'erro');
          return;
        }

        const blob = await resposta.blob();
        const urlObjeto = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = urlObjeto;
        link.download = 'dashboard_export.xlsx';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(urlObjeto);
      } catch (erro) {
        mostrarAviso('Erro de conexão ao exportar.', 'erro');
      } finally {
        botao.disabled = false;
        botao.textContent = textoOriginal;
      }
    });
  }

  // ---------------------------------------------------------------
  // Período padrão (últimos 30 dias) e carga inicial
  // ---------------------------------------------------------------
  function definirPeriodoPadrao() {
    const hoje = new Date();
    const trintaDiasAtras = new Date();
    trintaDiasAtras.setDate(hoje.getDate() - 30);
    document.getElementById('filtro-data-de').value = trintaDiasAtras.toISOString().slice(0, 10);
    document.getElementById('filtro-data-ate').value = hoje.toISOString().slice(0, 10);
  }

  definirPeriodoPadrao();
  await carregarCatalogos();
  await configurarBuscaPessoa();
  configurarBuscaLocal();
  await pesquisar();
});
