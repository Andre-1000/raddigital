/*
 * Gerenciar Usuários — tela única que substitui as antigas telas
 * separadas "Gerenciar Usuários" e "Gerenciar Colaboradores".
 *
 * 30/07/2026: busca e filtros só aplicam ao clicar em "Pesquisar" —
 * nada é buscado/mostrado antes disso. Filtros "vazios" (nenhuma
 * caixa marcada) significam "todos", tanto para Perfil quanto Status.
 * Ações da tabela viram ícones com tooltip (title) em vez de botão
 * com texto. Coluna "Senha" foi removida da tabela.
 */
document.addEventListener('DOMContentLoaded', function () {
  if (!RadAuth.exigirSessao()) return;
  if (!RadAuth.temPerfil('supervisor', 'administrador')) {
    window.location.href = '/inicio/';
    return;
  }
  document.getElementById('conteudo-protegido').style.display = '';

  const souAdministrador = RadAuth.temPerfil('administrador');
  if (!souAdministrador) {
    // Supervisor nao pode atribuir/ver o checkbox de Administrador
    // nos formularios (PRM-016/017/024), mas continua vendo a coluna
    // de perfis normalmente na tabela.
    document.getElementById('label-perfil-novo-admin').style.display = 'none';
    document.getElementById('label-filtro-admin').style.display = 'none';
    document.getElementById('label-perfil-editar-admin').style.display = 'none';
  }

  let pessoaEmEdicao = null;
  let pessoaEmExclusao = null;
  let pesquisaJaFeita = false;

  const avisoCriar = document.getElementById('aviso-criar');
  const avisoImportar = document.getElementById('aviso-importar');
  const avisoLista = document.getElementById('aviso-lista');
  const corpoTabela = document.getElementById('corpo-tabela-pessoas');
  const mensagemVazia = document.getElementById('mensagem-vazia');
  const mensagemInicial = document.getElementById('mensagem-inicial');

  function html(strings, ...valores) {
    return strings.reduce((acc, str, i) => acc + str + (valores[i] ?? ''), '');
  }

  function escapar(texto) {
    const div = document.createElement('div');
    div.textContent = texto ?? '';
    return div.innerHTML;
  }

  function mostrarAviso(container, mensagem, tipo) {
    container.innerHTML = `<div class="aviso aviso--${tipo}">${escapar(mensagem)}</div>`;
  }

  function limparAviso(container) {
    container.innerHTML = '';
  }

  // -------------------------------------------------------------
  // Ícones (SVG inline, sem dependência externa) — cada um com
  // tooltip via title no <button> que o envolve.
  // -------------------------------------------------------------
  const ICONE_EDITAR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z"></path></svg>';
  const ICONE_ATIVAR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg>';
  const ICONE_DESATIVAR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.9" y1="4.9" x2="19.1" y2="19.1"></line></svg>';
  const ICONE_EXCLUIR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>';

  // -------------------------------------------------------------
  // Modal: Como importar
  // -------------------------------------------------------------
  const modalComoImportar = document.getElementById('modal-como-importar');
  document.getElementById('botao-como-importar').addEventListener('click', function () {
    modalComoImportar.style.display = 'flex';
  });
  document.getElementById('botao-fechar-como-importar').addEventListener('click', function () {
    modalComoImportar.style.display = 'none';
  });

  // -------------------------------------------------------------
  // Cadastro manual — 30/07/2026: email obrigatorio, tudo numa unica
  // chamada (POST /colaboradores/ ja aceita email+perfis direto).
  // -------------------------------------------------------------
  document.getElementById('botao-criar-usuario').addEventListener('click', async function () {
    limparAviso(avisoCriar);

    const nome = document.getElementById('campo-novo-nome').value.trim();
    const matricula = document.getElementById('campo-novo-matricula').value.trim();
    const email = document.getElementById('campo-novo-email').value.trim();
    const perfis = [];
    if (document.getElementById('perfil-novo-usuario').checked) perfis.push('usuario');
    if (document.getElementById('perfil-novo-supervisor').checked) perfis.push('supervisor');
    if (souAdministrador && document.getElementById('perfil-novo-administrador').checked) {
      perfis.push('administrador');
    }

    if (!nome || !matricula) {
      mostrarAviso(avisoCriar, 'Preencha nome e matrícula.', 'erro');
      return;
    }
    if (!email) {
      mostrarAviso(avisoCriar, 'O e-mail é obrigatório.', 'erro');
      return;
    }

    const botao = document.getElementById('botao-criar-usuario');
    botao.disabled = true;
    try {
      const resposta = await RadAuth.requisicaoAutenticada('/colaboradores/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ registro_empresa: matricula, nome, email, perfis }),
      });
      const dados = await resposta.json();

      if (!resposta.ok) {
        const mensagem = (dados.erros || []).map((e) => e.mensagem).join(' ') || 'Não foi possível cadastrar.';
        mostrarAviso(avisoCriar, mensagem, 'erro');
        return;
      }

      mostrarAviso(avisoCriar, `${nome} cadastrado com sucesso.`, 'sucesso');
      document.getElementById('campo-novo-nome').value = '';
      document.getElementById('campo-novo-matricula').value = '';
      document.getElementById('campo-novo-email').value = '';
      document.getElementById('perfil-novo-usuario').checked = true;
      document.getElementById('perfil-novo-supervisor').checked = false;
      document.getElementById('perfil-novo-administrador').checked = false;
      if (pesquisaJaFeita) await pesquisar();
    } catch (erro) {
      mostrarAviso(avisoCriar, 'Erro de conexão ao cadastrar.', 'erro');
    } finally {
      botao.disabled = false;
    }
  });

  // -------------------------------------------------------------
  // Importação CSV
  // -------------------------------------------------------------
  document.getElementById('botao-importar').addEventListener('click', async function () {
    limparAviso(avisoImportar);
    const campoArquivo = document.getElementById('campo-arquivo-importar');
    const arquivo = campoArquivo.files[0];
    if (!arquivo) {
      mostrarAviso(avisoImportar, 'Selecione um arquivo CSV.', 'erro');
      return;
    }

    const formData = new FormData();
    formData.append('arquivo', arquivo);

    const botao = document.getElementById('botao-importar');
    botao.disabled = true;
    botao.textContent = 'Importando…';
    try {
      const resposta = await RadAuth.requisicaoAutenticada('/colaboradores/importar/', {
        method: 'POST',
        body: formData,
      });
      const dados = await resposta.json();

      if (!resposta.ok) {
        mostrarAviso(avisoImportar, dados.erro || 'Não foi possível importar.', 'erro');
        return;
      }

      let mensagem = `${dados.criados} criado(s), ${dados.atualizados} atualizado(s).`;
      if (dados.erros && dados.erros.length > 0) {
        mensagem += ` ${dados.erros.length} linha(s) com problema.`;
        mostrarAviso(avisoImportar, mensagem, 'atencao');
      } else {
        mostrarAviso(avisoImportar, mensagem, 'sucesso');
      }
      campoArquivo.value = '';
      if (pesquisaJaFeita) await pesquisar();
    } catch (erro) {
      mostrarAviso(avisoImportar, 'Erro de conexão ao importar.', 'erro');
    } finally {
      botao.disabled = false;
      botao.textContent = 'Importar';
    }
  });

  // -------------------------------------------------------------
  // Listagem — só carrega/mostra ao clicar em "Pesquisar"
  // -------------------------------------------------------------
  function seloStatus(ativo) {
    return ativo
      ? '<span class="selo selo--online">Ativo</span>'
      : '<span class="selo selo--offline">Inativo</span>';
  }

  function seloPerfil(perfil) {
    const rotulos = { usuario: 'Usuário', supervisor: 'Supervisor', administrador: 'Administrador' };
    return `<span class="selo selo--online" style="margin-right:0.6rem;">${rotulos[perfil] || perfil}</span>`;
  }

  function pessoaCorrespondeAosFiltros(pessoa, termoBusca, perfisPermitidos, statusPermitidos) {
    if (termoBusca) {
      const alvo = `${pessoa.nome} ${pessoa.registro_empresa}`.toLowerCase();
      if (!alvo.includes(termoBusca.toLowerCase())) return false;
    }

    // "nenhum marcado" = sem filtro (todos passam)
    if (perfisPermitidos.size > 0) {
      const temPerfilPermitido = pessoa.perfis.some((p) => perfisPermitidos.has(p));
      if (pessoa.perfis.length === 0 && !perfisPermitidos.has('usuario')) return false;
      if (pessoa.perfis.length > 0 && !temPerfilPermitido) return false;
    }

    if (statusPermitidos.size > 0) {
      const statusDaPessoa = pessoa.ativo ? 'ativos' : 'inativos';
      if (!statusPermitidos.has(statusDaPessoa)) return false;
    }

    return true;
  }

  function linhaTabela(pessoa) {
    const podeGerenciarAdmin = souAdministrador || !pessoa.perfis.includes('administrador');
    const perfisHtml = pessoa.perfis.length
      ? pessoa.perfis.map(seloPerfil).join('')
      : '<span class="texto-suave" style="font-size:0.85rem;">Sem login</span>';

    const botoesAcao = podeGerenciarAdmin
      ? html`
        <button type="button" class="botao botao--secundaria botao-icone botao-editar-perfis"
                title="Editar perfis e e-mail"
                data-id="${pessoa.id}" data-usuario-id="${pessoa.usuario_id ?? ''}"
                data-nome="${escapar(pessoa.nome)}" data-perfis="${pessoa.perfis.join(',')}"
                data-email="${escapar(pessoa.email || '')}">
          ${ICONE_EDITAR}
        </button>
        <button type="button" class="botao botao--secundaria botao-icone botao-alternar-status"
                title="${pessoa.ativo ? 'Desativar' : 'Ativar'}"
                data-id="${pessoa.id}" data-ativo="${pessoa.ativo}">
          ${pessoa.ativo ? ICONE_DESATIVAR : ICONE_ATIVAR}
        </button>
        <button type="button" class="botao botao--perigo botao-icone botao-excluir"
                title="Excluir definitivamente"
                data-id="${pessoa.id}" data-nome="${escapar(pessoa.nome)}">
          ${ICONE_EXCLUIR}
        </button>`
      : '<span class="texto-suave" style="font-size:0.8rem;">Somente outro Administrador</span>';

    return html`
      <tr>
        <td>${escapar(pessoa.nome)}</td>
        <td>${escapar(pessoa.registro_empresa)}</td>
        <td>${pessoa.email ? escapar(pessoa.email) : '<span class="texto-suave">—</span>'}</td>
        <td>${perfisHtml}</td>
        <td>${seloStatus(pessoa.ativo)}</td>
        <td><div style="display:flex; gap:0.4rem; flex-wrap:wrap;">${botoesAcao}</div></td>
      </tr>`;
  }

  let todasAsPessoas = [];

  async function buscarTodasAsPessoas() {
    const resposta = await RadAuth.requisicaoAutenticada('/colaboradores/administrar/');
    if (!resposta.ok) throw new Error('Falha ao carregar lista');
    const dados = await resposta.json();
    return dados.colaboradores;
  }

  function renderizar() {
    const termoBusca = document.getElementById('campo-busca').value.trim();

    const perfisPermitidos = new Set();
    if (document.getElementById('filtro-perfil-usuario').checked) perfisPermitidos.add('usuario');
    if (document.getElementById('filtro-perfil-supervisor').checked) perfisPermitidos.add('supervisor');
    if (souAdministrador && document.getElementById('filtro-perfil-administrador').checked) {
      perfisPermitidos.add('administrador');
    }

    const statusPermitidos = new Set();
    if (document.getElementById('filtro-status-ativos').checked) statusPermitidos.add('ativos');
    if (document.getElementById('filtro-status-inativos').checked) statusPermitidos.add('inativos');

    const filtradas = todasAsPessoas.filter((p) =>
      pessoaCorrespondeAosFiltros(p, termoBusca, perfisPermitidos, statusPermitidos)
    );

    mensagemInicial.style.display = 'none';

    if (filtradas.length === 0) {
      corpoTabela.innerHTML = '';
      mensagemVazia.style.display = '';
      return;
    }
    mensagemVazia.style.display = 'none';
    corpoTabela.innerHTML = filtradas.map(linhaTabela).join('');

    corpoTabela.querySelectorAll('.botao-editar-perfis').forEach((botao) => {
      botao.addEventListener('click', () => abrirModalEditarPerfis(botao.dataset));
    });
    corpoTabela.querySelectorAll('.botao-alternar-status').forEach((botao) => {
      botao.addEventListener('click', () => alternarStatus(botao.dataset));
    });
    corpoTabela.querySelectorAll('.botao-excluir').forEach((botao) => {
      botao.addEventListener('click', () => abrirModalExcluir(botao.dataset));
    });
  }

  async function pesquisar() {
    limparAviso(avisoLista);
    const botaoPesquisar = document.getElementById('botao-pesquisar');
    botaoPesquisar.disabled = true;
    botaoPesquisar.textContent = 'Pesquisando…';
    try {
      todasAsPessoas = await buscarTodasAsPessoas();
      pesquisaJaFeita = true;
      renderizar();
    } catch (erro) {
      mostrarAviso(avisoLista, 'Erro de conexão ao pesquisar.', 'erro');
    } finally {
      botaoPesquisar.disabled = false;
      botaoPesquisar.textContent = 'Pesquisar';
    }
  }

  document.getElementById('botao-pesquisar').addEventListener('click', pesquisar);
  // Enter no campo de busca tambem pesquisa, sem precisar clicar no botao
  document.getElementById('campo-busca').addEventListener('keydown', function (evento) {
    if (evento.key === 'Enter') pesquisar();
  });

  // -------------------------------------------------------------
  // Editar perfis e e-mail
  // -------------------------------------------------------------
  const modalEditarPerfis = document.getElementById('modal-editar-perfis');
  const avisoEditarPerfis = document.getElementById('aviso-editar-perfis');

  function abrirModalEditarPerfis(dataset) {
    if (!dataset.usuarioId) {
      mostrarAviso(avisoLista, 'Esta pessoa ainda não tem login vinculado.', 'atencao');
      return;
    }
    pessoaEmEdicao = { id: dataset.id, usuarioId: dataset.usuarioId, nome: dataset.nome };
    document.getElementById('nome-pessoa-editar').textContent = dataset.nome;
    limparAviso(avisoEditarPerfis);

    document.getElementById('campo-email-editar').value = dataset.email || '';

    const perfisAtuais = dataset.perfis ? dataset.perfis.split(',') : [];
    document.getElementById('perfil-editar-usuario').checked = perfisAtuais.includes('usuario');
    document.getElementById('perfil-editar-supervisor').checked = perfisAtuais.includes('supervisor');
    document.getElementById('perfil-editar-administrador').checked = perfisAtuais.includes('administrador');

    modalEditarPerfis.style.display = 'flex';
  }

  document.getElementById('botao-cancelar-editar-perfis').addEventListener('click', () => {
    modalEditarPerfis.style.display = 'none';
    pessoaEmEdicao = null;
  });

  document.getElementById('botao-salvar-perfis').addEventListener('click', async function () {
    if (!pessoaEmEdicao) return;
    limparAviso(avisoEditarPerfis);

    const perfis = [];
    if (document.getElementById('perfil-editar-usuario').checked) perfis.push('usuario');
    if (document.getElementById('perfil-editar-supervisor').checked) perfis.push('supervisor');
    if (souAdministrador && document.getElementById('perfil-editar-administrador').checked) {
      perfis.push('administrador');
    }

    if (perfis.length === 0) {
      mostrarAviso(avisoEditarPerfis, 'Selecione ao menos 1 perfil.', 'erro');
      return;
    }

    const email = document.getElementById('campo-email-editar').value.trim();

    const botao = document.getElementById('botao-salvar-perfis');
    botao.disabled = true;
    try {
      const resposta = await RadAuth.requisicaoAutenticada(
        `/usuarios/administrar/${pessoaEmEdicao.usuarioId}/editar/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ perfis, email }),
        }
      );
      const dados = await resposta.json();
      if (!resposta.ok) {
        const mensagem = (dados.erros || []).map((e) => e.mensagem).join(' ') || dados.erro || 'Não foi possível salvar.';
        mostrarAviso(avisoEditarPerfis, mensagem, 'erro');
        return;
      }
      modalEditarPerfis.style.display = 'none';
      pessoaEmEdicao = null;
      await pesquisar();
    } catch (erro) {
      mostrarAviso(avisoEditarPerfis, 'Erro de conexão ao salvar.', 'erro');
    } finally {
      botao.disabled = false;
    }
  });

  // -------------------------------------------------------------
  // Ativar / desativar
  // -------------------------------------------------------------
  async function alternarStatus(dataset) {
    const ativoAtual = dataset.ativo === 'true';
    try {
      const resposta = await RadAuth.requisicaoAutenticada(`/colaboradores/${dataset.id}/editar/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ativo: !ativoAtual }),
      });
      if (!resposta.ok) {
        mostrarAviso(avisoLista, 'Não foi possível alterar o status.', 'erro');
        return;
      }
      await pesquisar();
    } catch (erro) {
      mostrarAviso(avisoLista, 'Erro de conexão ao alterar status.', 'erro');
    }
  }

  // -------------------------------------------------------------
  // Excluir
  // -------------------------------------------------------------
  const modalExcluir = document.getElementById('modal-excluir-pessoa');

  function abrirModalExcluir(dataset) {
    pessoaEmExclusao = dataset.id;
    document.getElementById('nome-pessoa-excluir').textContent = dataset.nome;
    modalExcluir.style.display = 'flex';
  }

  document.getElementById('botao-cancelar-exclusao').addEventListener('click', () => {
    modalExcluir.style.display = 'none';
    pessoaEmExclusao = null;
  });

  document.getElementById('botao-confirmar-exclusao').addEventListener('click', async function () {
    if (!pessoaEmExclusao) return;
    const botao = document.getElementById('botao-confirmar-exclusao');
    botao.disabled = true;
    try {
      const resposta = await RadAuth.requisicaoAutenticada(`/colaboradores/${pessoaEmExclusao}/excluir/`, {
        method: 'POST',
      });
      if (!resposta.ok) {
        mostrarAviso(avisoLista, 'Não foi possível excluir.', 'erro');
        return;
      }
      modalExcluir.style.display = 'none';
      pessoaEmExclusao = null;
      await pesquisar();
    } catch (erro) {
      mostrarAviso(avisoLista, 'Erro de conexão ao excluir.', 'erro');
    } finally {
      botao.disabled = false;
    }
  });
});
