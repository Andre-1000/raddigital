/*
 * Gerenciar Usuários — tela única que substitui as antigas telas
 * separadas "Gerenciar Usuários" e "Gerenciar Colaboradores".
 *
 * 30/07/2026: busca e filtros só aplicam ao clicar em "Pesquisar" —
 * nada é buscado/mostrado antes disso. Filtros "vazios" (nenhuma
 * caixa marcada) significam "todos", tanto para Perfil quanto Status.
 * Ações da tabela viram ícones com tooltip (title) em vez de botão
 * com texto. Coluna "Senha" foi removida da tabela.
 *
 * 21/08/2026: tela reorganizada em 3 abas -- "Buscar" (padrão, aberta
 * ao entrar na tela), "Cadastro de Usuário" e "Sessões". As duas
 * últimas são exclusivas do Administrador (o Supervisor via Cadastro
 * antes mas o backend sempre rejeitava com 403 -- bug corrigido
 * escondendo a aba, já que o Supervisor nunca teve permissão real de
 * criar/editar/excluir/importar colaborador, ver colaboradores/views.py).
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
  } else {
    // 21/08/2026: abas "Cadastro de Usuário" e "Sessões" só existem
    // para o Administrador.
    document.getElementById('aba-nav-cadastro').style.display = '';
    document.getElementById('aba-nav-sessoes').style.display = '';
  }

  // -------------------------------------------------------------
  // Navegação em abas
  // -------------------------------------------------------------
  const botoesAba = document.querySelectorAll('.abas__botao');
  const paineisAba = document.querySelectorAll('.abas__painel');

  function abrirAba(nomeAba) {
    botoesAba.forEach(function (botao) {
      botao.classList.toggle('abas__botao--ativa', botao.dataset.aba === nomeAba);
    });
    paineisAba.forEach(function (painel) {
      painel.style.display = painel.dataset.painel === nomeAba ? '' : 'none';
    });
  }

  botoesAba.forEach(function (botao) {
    botao.addEventListener('click', function () {
      abrirAba(botao.dataset.aba);
    });
  });

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

  function formatarDataHora(isoString) {
    const data = new Date(isoString);
    return data.toLocaleString('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  // -------------------------------------------------------------
  // Ícones (SVG inline, sem dependência externa) — cada um com
  // tooltip via title no <button> que o envolve.
  // -------------------------------------------------------------
  const ICONE_EDITAR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z"></path></svg>';
  const ICONE_ATIVAR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg>';
  const ICONE_DESATIVAR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.9" y1="4.9" x2="19.1" y2="19.1"></line></svg>';
  const ICONE_EXCLUIR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>';
  const ICONE_SENHA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="15.5" r="5.5"></circle><path d="m21 2-9.6 9.6"></path><path d="m15.5 7.5 3 3L22 7l-3-3"></path></svg>';

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

    const botaoSenhaTemp = souAdministrador && pessoa.usuario_id
      ? html`
        <button type="button" class="botao botao--secundaria botao-icone botao-senha-temporaria"
                title="Definir senha temporária"
                data-usuario-id="${pessoa.usuario_id}" data-nome="${escapar(pessoa.nome)}">
          ${ICONE_SENHA}
        </button>`
      : '';

    const botoesAcao = podeGerenciarAdmin
      ? html`
        <button type="button" class="botao botao--secundaria botao-icone botao-editar-perfis"
                title="Editar"
                data-id="${pessoa.id}" data-usuario-id="${pessoa.usuario_id ?? ''}"
                data-nome="${escapar(pessoa.nome)}" data-registro-empresa="${escapar(pessoa.registro_empresa)}"
                data-perfis="${pessoa.perfis.join(',')}"
                data-email="${escapar(pessoa.email || '')}">
          ${ICONE_EDITAR}
        </button>
        <button type="button" class="botao botao--secundaria botao-icone botao-alternar-status"
                title="${pessoa.ativo ? 'Desativar' : 'Ativar'}"
                data-id="${pessoa.id}" data-ativo="${pessoa.ativo}">
          ${pessoa.ativo ? ICONE_DESATIVAR : ICONE_ATIVAR}
        </button>
        ${botaoSenhaTemp}
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
    corpoTabela.querySelectorAll('.botao-senha-temporaria').forEach((botao) => {
      botao.addEventListener('click', () => definirSenhaTemporaria(botao.dataset));
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

    document.getElementById('campo-nome-editar').value = dataset.nome || '';
    document.getElementById('campo-matricula-editar').value = dataset.registroEmpresa || '';
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

    const nome = document.getElementById('campo-nome-editar').value.trim();
    const matricula = document.getElementById('campo-matricula-editar').value.trim();
    const email = document.getElementById('campo-email-editar').value.trim();
    const perfis = [];
    if (document.getElementById('perfil-editar-usuario').checked) perfis.push('usuario');
    if (document.getElementById('perfil-editar-supervisor').checked) perfis.push('supervisor');
    if (souAdministrador && document.getElementById('perfil-editar-administrador').checked) {
      perfis.push('administrador');
    }

    if (!nome || !matricula) {
      mostrarAviso(avisoEditarPerfis, 'Preencha nome e matrícula.', 'erro');
      return;
    }
    if (perfis.length === 0) {
      mostrarAviso(avisoEditarPerfis, 'Selecione ao menos 1 perfil.', 'erro');
      return;
    }

    const botao = document.getElementById('botao-salvar-perfis');
    botao.disabled = true;
    try {
      // 30/07/2026: passo 1 -- nome/matricula/status sao dados do
      // Colaborador. Se a matricula mudar, o login vinculado tambem
      // muda (colaboradores/views.py::editar recria o vinculo) -- por
      // isso o passo 2 usa o usuario_id que VOLTA na resposta deste
      // passo, nunca o usuario_id antigo capturado quando o modal
      // abriu (que pode ter ficado obsoleto).
      const respostaColaborador = await RadAuth.requisicaoAutenticada(
        `/colaboradores/${pessoaEmEdicao.id}/editar/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ registro_empresa: matricula, nome }),
        }
      );
      const dadosColaborador = await respostaColaborador.json();
      if (!respostaColaborador.ok) {
        const mensagem = (dadosColaborador.erros || []).map((e) => e.mensagem).join(' ') || dadosColaborador.erro || 'Não foi possível salvar nome/matrícula.';
        mostrarAviso(avisoEditarPerfis, mensagem, 'erro');
        return;
      }

      // Passo 2 -- perfis e e-mail sao dados do Usuario, usando o
      // usuario_id atual (pode ter mudado no passo 1).
      const usuarioIdAtual = dadosColaborador.usuario_id;
      const respostaUsuario = await RadAuth.requisicaoAutenticada(
        `/usuarios/administrar/${usuarioIdAtual}/editar/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ perfis, email }),
        }
      );
      const dadosUsuario = await respostaUsuario.json();
      if (!respostaUsuario.ok) {
        const mensagem = (dadosUsuario.erros || []).map((e) => e.mensagem).join(' ') || dadosUsuario.erro || 'Não foi possível salvar perfis/e-mail.';
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

  // -------------------------------------------------------------
  // Senha temporária (25/08/2026, exclusivo do Administrador) --
  // via de emergência quando "Esqueci minha senha" não chega (SMTP
  // fora do ar/mal configurado). Pede confirmação (window.confirm --
  // ação sensível o bastante pra merecer uma pausa, mas simples o
  // bastante pra não precisar de um modal próprio só pra isso), gera
  // a senha no backend, e mostra ela UMA VEZ no modal de resultado.
  // -------------------------------------------------------------
  const modalSenhaTemporaria = document.getElementById('modal-senha-temporaria');
  const avisoCopiarSenhaTemp = document.getElementById('aviso-copiar-senha-temp');

  async function definirSenhaTemporaria(dataset) {
    const confirmou = window.confirm(
      `Definir uma nova senha temporária para ${dataset.nome}? A senha atual dessa pessoa deixa de funcionar imediatamente.`
    );
    if (!confirmou) return;

    try {
      const resposta = await RadAuth.requisicaoAutenticada(
        `/usuarios/administrar/${dataset.usuarioId}/definir-senha-temporaria/`,
        { method: 'POST' }
      );
      const dados = await resposta.json();

      if (!resposta.ok) {
        mostrarAviso(avisoLista, dados.erro || 'Não foi possível gerar a senha temporária.', 'erro');
        return;
      }

      document.getElementById('nome-pessoa-senha-temp').textContent = dataset.nome;
      document.getElementById('valor-senha-temporaria').textContent = dados.senha_temporaria;
      avisoCopiarSenhaTemp.innerHTML = '';
      modalSenhaTemporaria.style.display = 'flex';
    } catch (erro) {
      mostrarAviso(avisoLista, 'Erro de conexão ao gerar a senha temporária.', 'erro');
    }
  }

  document.getElementById('botao-copiar-senha-temporaria').addEventListener('click', async function () {
    const valor = document.getElementById('valor-senha-temporaria').textContent;
    try {
      await navigator.clipboard.writeText(valor);
      avisoCopiarSenhaTemp.innerHTML = '<div class="aviso aviso--sucesso">Copiado.</div>';
    } catch (erro) {
      avisoCopiarSenhaTemp.innerHTML = '<div class="aviso aviso--erro">Não foi possível copiar automaticamente — selecione o texto manualmente.</div>';
    }
  });

  document.getElementById('botao-fechar-senha-temporaria').addEventListener('click', function () {
    modalSenhaTemporaria.style.display = 'none';
    document.getElementById('valor-senha-temporaria').textContent = '';
  });

  // -------------------------------------------------------------
  // Aba Sessões (Administrador) -- 21/08/2026
  // -------------------------------------------------------------
  if (souAdministrador) {
    const avisoSessoes = document.getElementById('aviso-sessoes');
    const corpoTabelaSessoes = document.getElementById('corpo-tabela-sessoes');
    const mensagemVaziaSessoes = document.getElementById('mensagem-vazia-sessoes');
    const mensagemInicialSessoes = document.getElementById('mensagem-inicial-sessoes');
    const campoBuscaSessoes = document.getElementById('campo-busca-sessoes');
    const botaoPesquisarSessoes = document.getElementById('botao-pesquisar-sessoes');

    function linhaSessao(sessao) {
      const acao = sessao.esta_sessao
        ? '<span class="texto-suave" style="font-size:0.8rem;">Esta sessão</span>'
        : html`<button type="button" class="botao botao--perigo botao-encerrar-sessao"
                  style="width:auto; min-height:36px; padding:0 1rem; font-size:0.85rem;"
                  data-id="${sessao.id}">
                Encerrar
              </button>`;

      return html`
        <tr>
          <td>${escapar(sessao.nome)}</td>
          <td>${escapar(sessao.login)}</td>
          <td>${escapar(sessao.dispositivo)}</td>
          <td>${formatarDataHora(sessao.criado_em)}</td>
          <td>${formatarDataHora(sessao.validade)}</td>
          <td>${acao}</td>
        </tr>`;
    }

    async function pesquisarSessoes() {
      limparAviso(avisoSessoes);
      mensagemInicialSessoes.style.display = 'none';
      botaoPesquisarSessoes.disabled = true;
      botaoPesquisarSessoes.textContent = 'Pesquisando…';
      try {
        const termo = campoBuscaSessoes.value.trim();
        const parametros = new URLSearchParams();
        if (termo) parametros.set('busca', termo);

        const resposta = await RadAuth.requisicaoAutenticada(`/usuarios/sessoes-ativas/?${parametros.toString()}`);
        if (!resposta.ok) {
          mostrarAviso(avisoSessoes, 'Não foi possível carregar as sessões.', 'erro');
          return;
        }
        const dados = await resposta.json();

        if (dados.sessoes.length === 0) {
          corpoTabelaSessoes.innerHTML = '';
          mensagemVaziaSessoes.style.display = '';
          return;
        }
        mensagemVaziaSessoes.style.display = 'none';
        corpoTabelaSessoes.innerHTML = dados.sessoes.map(linhaSessao).join('');

        corpoTabelaSessoes.querySelectorAll('.botao-encerrar-sessao').forEach((botao) => {
          botao.addEventListener('click', () => encerrarSessao(botao.dataset.id));
        });
      } catch (erro) {
        mostrarAviso(avisoSessoes, 'Erro de conexão ao pesquisar sessões.', 'erro');
      } finally {
        botaoPesquisarSessoes.disabled = false;
        botaoPesquisarSessoes.textContent = 'Pesquisar';
      }
    }

    async function encerrarSessao(idToken) {
      try {
        const resposta = await RadAuth.requisicaoAutenticada(`/usuarios/sessoes-ativas/${idToken}/encerrar/`, {
          method: 'POST',
        });
        const dados = await resposta.json();
        if (!resposta.ok) {
          mostrarAviso(avisoSessoes, dados.erro || 'Não foi possível encerrar a sessão.', 'erro');
          return;
        }
        await pesquisarSessoes();
      } catch (erro) {
        mostrarAviso(avisoSessoes, 'Erro de conexão ao encerrar a sessão.', 'erro');
      }
    }

    botaoPesquisarSessoes.addEventListener('click', pesquisarSessoes);
    campoBuscaSessoes.addEventListener('keydown', function (evento) {
      if (evento.key === 'Enter') pesquisarSessoes();
    });

    // -----------------------------------------------------------
    // Histórico de senhas temporárias (25/08/2026) -- auditoria de
    // quem gerou senha temporária pra quem. Carregado junto com a
    // primeira abertura da aba Sessões, sem precisar de botão
    // próprio (volume baixo, uso de emergência).
    // -----------------------------------------------------------
    const avisoLogSenhaTemp = document.getElementById('aviso-log-senha-temp');
    const corpoTabelaLogSenhaTemp = document.getElementById('corpo-tabela-log-senha-temp');
    const mensagemVaziaLogSenhaTemp = document.getElementById('mensagem-vazia-log-senha-temp');

    function linhaLogSenhaTemp(entrada) {
      return html`
        <tr>
          <td>${escapar(entrada.administrador)}</td>
          <td>${escapar(entrada.usuario_alvo)}</td>
          <td>${formatarDataHora(entrada.criado_em)}</td>
        </tr>`;
    }

    async function carregarLogSenhaTemporaria() {
      limparAviso(avisoLogSenhaTemp);
      try {
        const resposta = await RadAuth.requisicaoAutenticada('/usuarios/administrar/log-senha-temporaria/');
        if (!resposta.ok) {
          mostrarAviso(avisoLogSenhaTemp, 'Não foi possível carregar o histórico.', 'erro');
          return;
        }
        const dados = await resposta.json();

        if (dados.entradas.length === 0) {
          corpoTabelaLogSenhaTemp.innerHTML = '';
          mensagemVaziaLogSenhaTemp.style.display = '';
          return;
        }
        mensagemVaziaLogSenhaTemp.style.display = 'none';
        corpoTabelaLogSenhaTemp.innerHTML = dados.entradas.map(linhaLogSenhaTemp).join('');
      } catch (erro) {
        mostrarAviso(avisoLogSenhaTemp, 'Erro de conexão ao carregar o histórico.', 'erro');
      }
    }

    // Carrega a lista completa assim que a aba "Sessões" é aberta pela
    // primeira vez -- não precisa esperar a pessoa clicar em
    // "Pesquisar" de novo se ela só quer ver "quem está online agora".
    let sessoesJaCarregadas = false;
    document.getElementById('aba-nav-sessoes').addEventListener('click', function () {
      if (!sessoesJaCarregadas) {
        sessoesJaCarregadas = true;
        pesquisarSessoes();
        carregarLogSenhaTemporaria();
      }
    });
  }
});
