/*
 * Gerenciar Usuários — tela única que substitui as antigas telas
 * separadas "Gerenciar Usuários" e "Gerenciar Colaboradores".
 *
 * Usa os endpoints do app colaboradores como fonte principal (cada
 * colaborador já traz login/perfis/status do usuário vinculado, ver
 * colaboradores/views.py::_serializar). Editar perfis usa o endpoint
 * de usuarios (usuarios/administrar/<id>/editar/), porque perfil e'
 * um dado do Usuario, nao do Colaborador.
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

  const avisoCriar = document.getElementById('aviso-criar');
  const avisoImportar = document.getElementById('aviso-importar');
  const avisoLista = document.getElementById('aviso-lista');
  const corpoTabela = document.getElementById('corpo-tabela-pessoas');
  const mensagemVazia = document.getElementById('mensagem-vazia');

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
  // Cadastro manual
  // -------------------------------------------------------------
  document.getElementById('botao-criar-usuario').addEventListener('click', async function () {
    limparAviso(avisoCriar);

    const nome = document.getElementById('campo-novo-nome').value.trim();
    const matricula = document.getElementById('campo-novo-matricula').value.trim();
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

    const botao = document.getElementById('botao-criar-usuario');
    botao.disabled = true;
    try {
      // 1) cria o colaborador — isso ja cria o login com perfil
      //    Usuario automaticamente (ver colaboradores/views.py::_garantir_usuario)
      const resposta = await RadAuth.requisicaoAutenticada('/colaboradores/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ registro_empresa: matricula, nome }),
      });
      const dados = await resposta.json();

      if (!resposta.ok) {
        const mensagem = (dados.erros || []).map((e) => e.mensagem).join(' ') || 'Não foi possível cadastrar.';
        mostrarAviso(avisoCriar, mensagem, 'erro');
        return;
      }

      // 2) se pediram perfis alem do padrao (Usuario), atualiza
      const perfisDiferentesDoPadrao = perfis.length !== 1 || perfis[0] !== 'usuario';
      if (perfisDiferentesDoPadrao && dados.usuario_id) {
        await RadAuth.requisicaoAutenticada(`/usuarios/administrar/${dados.usuario_id}/editar/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ perfis }),
        });
      }

      mostrarAviso(avisoCriar, `${nome} cadastrado com sucesso.`, 'sucesso');
      document.getElementById('campo-novo-nome').value = '';
      document.getElementById('campo-novo-matricula').value = '';
      document.getElementById('perfil-novo-usuario').checked = true;
      document.getElementById('perfil-novo-supervisor').checked = false;
      document.getElementById('perfil-novo-administrador').checked = false;
      await carregarLista();
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
      await carregarLista();
    } catch (erro) {
      mostrarAviso(avisoImportar, 'Erro de conexão ao importar.', 'erro');
    } finally {
      botao.disabled = false;
      botao.textContent = 'Importar';
    }
  });

  // -------------------------------------------------------------
  // Listagem, busca e filtros
  // -------------------------------------------------------------
  function seloStatus(ativo) {
    return ativo
      ? '<span class="selo selo--online">Ativo</span>'
      : '<span class="selo selo--offline">Inativo</span>';
  }

  function seloPerfil(perfil) {
    const rotulos = { usuario: 'Usuário', supervisor: 'Supervisor', administrador: 'Administrador' };
    return `<span class="selo selo--online" style="margin-right:0.3rem;">${rotulos[perfil] || perfil}</span>`;
  }

  function pessoaCorrespondeAosFiltros(pessoa, termoBusca, perfisPermitidos, mostrarInativos) {
    if (!mostrarInativos && !pessoa.ativo) return false;

    if (termoBusca) {
      const alvo = `${pessoa.nome} ${pessoa.registro_empresa}`.toLowerCase();
      if (!alvo.includes(termoBusca.toLowerCase())) return false;
    }

    if (pessoa.perfis.length === 0) return true; // sem perfil ainda aparece (cadastro incompleto)
    return pessoa.perfis.some((p) => perfisPermitidos.has(p));
  }

  function linhaTabela(pessoa) {
    const podeGerenciarAdmin = souAdministrador || !pessoa.perfis.includes('administrador');
    const perfisHtml = pessoa.perfis.length
      ? pessoa.perfis.map(seloPerfil).join('')
      : '<span class="texto-suave" style="font-size:0.85rem;">Sem login</span>';

    const botoesAcao = podeGerenciarAdmin
      ? html`
        <button type="button" class="botao botao--secundaria botao-editar-perfis"
                data-id="${pessoa.id}" data-usuario-id="${pessoa.usuario_id ?? ''}"
                data-nome="${escapar(pessoa.nome)}" data-perfis="${pessoa.perfis.join(',')}"
                style="width:auto; min-height:36px; padding:0 0.75rem; font-size:0.85rem;">
          Editar perfis
        </button>
        <button type="button" class="botao botao--secundaria botao-alternar-status"
                data-id="${pessoa.id}" data-ativo="${pessoa.ativo}"
                style="width:auto; min-height:36px; padding:0 0.75rem; font-size:0.85rem;">
          ${pessoa.ativo ? 'Desativar' : 'Ativar'}
        </button>
        <button type="button" class="botao botao--perigo botao-excluir"
                data-id="${pessoa.id}" data-nome="${escapar(pessoa.nome)}"
                style="width:auto; min-height:36px; padding:0 0.75rem; font-size:0.85rem;">
          Excluir
        </button>`
      : '<span class="texto-suave" style="font-size:0.8rem;">Editar/excluir Admin — somente outro Administrador</span>';

    return html`
      <tr>
        <td>${escapar(pessoa.nome)}</td>
        <td>${escapar(pessoa.registro_empresa)}</td>
        <td>${perfisHtml}</td>
        <td>${seloStatus(pessoa.ativo)}</td>
        <td><div style="display:flex; gap:0.4rem; flex-wrap:wrap;">${botoesAcao}</div></td>
      </tr>`;
  }

  let todasAsPessoas = [];

  async function carregarLista() {
    limparAviso(avisoLista);
    try {
      const resposta = await RadAuth.requisicaoAutenticada('/colaboradores/administrar/');
      if (!resposta.ok) {
        mostrarAviso(avisoLista, 'Não foi possível carregar a lista.', 'erro');
        return;
      }
      const dados = await resposta.json();
      todasAsPessoas = dados.colaboradores;
      aplicarFiltrosERenderizar();
    } catch (erro) {
      mostrarAviso(avisoLista, 'Erro de conexão ao carregar a lista.', 'erro');
    }
  }

  function aplicarFiltrosERenderizar() {
    const termoBusca = document.getElementById('campo-busca').value.trim();
    const mostrarInativos = document.getElementById('filtro-inativos').checked;

    const perfisPermitidos = new Set();
    if (document.getElementById('filtro-usuario').checked) perfisPermitidos.add('usuario');
    if (document.getElementById('filtro-supervisor').checked) perfisPermitidos.add('supervisor');
    if (souAdministrador && document.getElementById('filtro-administrador').checked) {
      perfisPermitidos.add('administrador');
    } else if (!souAdministrador) {
      perfisPermitidos.add('administrador'); // supervisor sempre ve admins na lista (so nao gerencia)
    }

    const filtradas = todasAsPessoas.filter((p) =>
      pessoaCorrespondeAosFiltros(p, termoBusca, perfisPermitidos, mostrarInativos)
    );

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

  document.getElementById('campo-busca').addEventListener('input', aplicarFiltrosERenderizar);
  ['filtro-usuario', 'filtro-supervisor', 'filtro-administrador', 'filtro-inativos'].forEach((id) => {
    const elemento = document.getElementById(id);
    if (elemento) elemento.addEventListener('change', aplicarFiltrosERenderizar);
  });

  // -------------------------------------------------------------
  // Editar perfis
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

    const botao = document.getElementById('botao-salvar-perfis');
    botao.disabled = true;
    try {
      const resposta = await RadAuth.requisicaoAutenticada(
        `/usuarios/administrar/${pessoaEmEdicao.usuarioId}/editar/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ perfis }),
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
      await carregarLista();
    } catch (erro) {
      mostrarAviso(avisoEditarPerfis, 'Erro de conexão ao salvar.', 'erro');
    } finally {
      botao.disabled = false;
    }
  });

  // -------------------------------------------------------------
  // Ativar / desativar (usa o endpoint de colaboradores, que e' a
  // fonte "oficial" de status usada tambem na busca do RAD)
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
      await carregarLista();
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
      await carregarLista();
    } catch (erro) {
      mostrarAviso(avisoLista, 'Erro de conexão ao excluir.', 'erro');
    } finally {
      botao.disabled = false;
    }
  });

  carregarLista();
});
