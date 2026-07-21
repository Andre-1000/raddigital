/*
 * Gerenciar Usuarios — Supervisor e Administrador (EFD secao 4.4).
 *
 * Correcoes aplicadas vs versao anterior:
 * - ES6+ (const/let, arrow functions, template literals)
 * - Objeto usuario mantido em memoria — sem leitura fragil do DOM
 * - Edicao inline no card (padrao gerenciar_colaboradores)
 * - Botoes desabilitados durante fetch com finally
 * - Ativar/desativar atualiza card especifico sem recarregar lista
 * - Busca por login em tempo real (sem nova requisicao)
 * - Filtro por perfil e status
 * - Estado de carregamento na lista
 * - Login nao e editavel apos criacao (identificador de autenticacao)
 * - Supervisor ve admins mas ve nota "nao pode gerenciar"
 * - Backend retorna pode_gerenciar por usuario
 */
document.addEventListener('DOMContentLoaded', async () => {
  if (!RadAuth.exigirSessao()) return;

  const ehAdmin = RadAuth.temPerfil('administrador');
  const ehSupervisor = RadAuth.temPerfil('supervisor');

  if (!ehSupervisor && !ehAdmin) {
    window.location.href = '/inicio/';
    return;
  }

  document.getElementById('conteudo-protegido').style.display = '';

  // Supervisor nao ve nem pode atribuir perfil Administrador (PRM-024)
  if (!ehAdmin) {
    document.getElementById('label-perfil-novo-admin').style.display = 'none';
    document.getElementById('label-filtro-admin').style.display = 'none';
  }

  const listaEl = document.getElementById('lista-usuarios');
  const avisoLista = document.getElementById('aviso-lista');
  const avisoCriar = document.getElementById('aviso-criar');

  // Todos os usuarios em memoria — nao lemos o DOM para obter dados
  let todosOsUsuarios = [];

  // ---------------------------------------------------------------------------
  // Utilitarios
  // ---------------------------------------------------------------------------

  const mensagemDeErro = (corpo, padrao) => {
    if (corpo?.erros?.length) return corpo.erros.map((e) => e.mensagem).join(' ');
    if (corpo?.erro) return corpo.erro;
    return padrao;
  };

  const exibirAviso = (el, texto, tipo) => {
    el.innerHTML = `<div class="aviso aviso--${tipo}">${texto}</div>`;
  };

  const rotuloPerfis = (perfis) => {
    const mapa = { usuario: 'Usuário', supervisor: 'Supervisor', administrador: 'Administrador' };
    return perfis.map((p) => mapa[p] || p).join(', ');
  };

  // ---------------------------------------------------------------------------
  // Listagem e filtragem em memoria (sem nova requisicao)
  // ---------------------------------------------------------------------------

  const carregarLista = async () => {
    avisoLista.innerHTML = '';
    listaEl.innerHTML = '<p class="texto-suave centro">Carregando…</p>';
    try {
      const resposta = await RadAuth.requisicaoAutenticada('/usuarios/administrar/');
      if (!resposta.ok) {
        exibirAviso(avisoLista, 'Não foi possível carregar os usuários.', 'erro');
        listaEl.innerHTML = '';
        return;
      }
      const dados = await resposta.json();
      todosOsUsuarios = dados.usuarios;
      renderizarLista();
    } catch (e) {
      exibirAviso(avisoLista, 'Erro de conexão ao carregar os usuários.', 'erro');
      listaEl.innerHTML = '';
    }
  };

  const renderizarLista = () => {
    listaEl.innerHTML = '';
    const busca = document.getElementById('campo-busca').value.trim().toLowerCase();
    const mostrarInativos = document.getElementById('filtro-inativos').checked;
    const filtroUsuario = document.getElementById('filtro-usuario').checked;
    const filtroSupervisor = document.getElementById('filtro-supervisor').checked;
    const filtroAdmin = document.getElementById('filtro-administrador')?.checked ?? false;

    const filtrados = todosOsUsuarios.filter((u) => {
      if (!mostrarInativos && !u.ativo) return false;
      if (busca && !u.login.toLowerCase().includes(busca)) return false;
      if (u.perfis.includes('usuario') && filtroUsuario) return true;
      if (u.perfis.includes('supervisor') && filtroSupervisor) return true;
      if (u.perfis.includes('administrador') && filtroAdmin) return true;
      return false;
    });

    if (filtrados.length === 0) {
      const vazio = document.createElement('p');
      vazio.className = 'texto-suave centro';
      vazio.textContent = 'Nenhum usuário encontrado.';
      listaEl.appendChild(vazio);
      return;
    }

    filtrados.forEach((u) => listaEl.appendChild(criarCartao(u)));
  };

  // Filtros em tempo real — sem bater na API
  document.getElementById('campo-busca').addEventListener('input', renderizarLista);
  document.getElementById('filtro-usuario').addEventListener('change', renderizarLista);
  document.getElementById('filtro-supervisor').addEventListener('change', renderizarLista);
  document.getElementById('filtro-inativos').addEventListener('change', renderizarLista);
  document.getElementById('filtro-administrador')?.addEventListener('change', renderizarLista);

  // ---------------------------------------------------------------------------
  // Card: modo visualizacao e edicao inline (padrao gerenciar_colaboradores)
  // ---------------------------------------------------------------------------

  const criarCartao = (usuario) => {
    const cartao = document.createElement('div');
    cartao.className = 'cartao';
    cartao.dataset.id = usuario.id;

    const desenharModoVisualizacao = () => {
      cartao.innerHTML = '';

      const topo = document.createElement('div');
      topo.style.cssText = 'display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;';
      topo.innerHTML = `
        <div>
          <strong>${usuario.login}</strong>
          <div class="texto-suave" style="font-size:0.85rem;">${rotuloPerfis(usuario.perfis)} &bull; Criado em ${usuario.data_criacao}</div>
        </div>
        <span class="selo ${usuario.ativo ? 'selo--online' : 'selo--offline'}">${usuario.ativo ? 'Ativo' : 'Inativo'}</span>
      `;
      cartao.appendChild(topo);

      const avisoLinha = document.createElement('div');
      cartao.appendChild(avisoLinha);

      const acoes = document.createElement('div');
      acoes.className = 'pilha';
      acoes.style.marginTop = '0.75rem';

      if (usuario.pode_gerenciar) {
        // Editar (edicao inline no card, sem modal)
        const botaoEditar = document.createElement('button');
        botaoEditar.type = 'button';
        botaoEditar.className = 'botao botao--secundaria';
        botaoEditar.textContent = 'Editar';
        botaoEditar.addEventListener('click', desenharModoEdicao);
        acoes.appendChild(botaoEditar);

        // Ativar / Desativar — atualiza so este card, sem recarregar a lista
        const botaoToggle = document.createElement('button');
        botaoToggle.type = 'button';
        botaoToggle.className = 'botao botao--secundaria';
        botaoToggle.textContent = usuario.ativo ? 'Desativar' : 'Ativar';
        botaoToggle.addEventListener('click', async () => {
          botaoToggle.disabled = true;
          try {
            const resposta = await RadAuth.requisicaoAutenticada(
              `/usuarios/administrar/${usuario.id}/editar/`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ perfis: usuario.perfis, ativo: !usuario.ativo }),
              }
            );
            if (!resposta.ok) {
              const corpo = await resposta.json().catch(() => ({}));
              avisoLinha.innerHTML = `<div class="aviso aviso--erro">${mensagemDeErro(corpo, 'Não foi possível atualizar.')}</div>`;
              return;
            }
            const atualizado = await resposta.json();
            Object.assign(usuario, atualizado); // atualiza objeto em memoria
            desenharModoVisualizacao(); // redesenha so este card
          } catch (e) {
            avisoLinha.innerHTML = '<div class="aviso aviso--erro">Erro de conexão.</div>';
          } finally {
            botaoToggle.disabled = false;
          }
        });
        acoes.appendChild(botaoToggle);

        // Excluir — nao aparece para o proprio usuario logado
        if (usuario.login !== RadAuth.obterSessao()?.login) {
          const botaoExcluir = document.createElement('button');
          botaoExcluir.type = 'button';
          botaoExcluir.className = 'botao botao--perigo';
          botaoExcluir.textContent = 'Excluir';
          botaoExcluir.addEventListener('click', () =>
            abrirModalExclusao(usuario, () => {
              todosOsUsuarios = todosOsUsuarios.filter((u) => u.id !== usuario.id);
              cartao.remove();
            })
          );
          acoes.appendChild(botaoExcluir);
        }
      } else {
        // Supervisor vendo Admin puro — mostra nota sem botoes
        const nota = document.createElement('p');
        nota.className = 'texto-suave';
        nota.style.fontSize = '0.85rem';
        nota.textContent = 'Somente Administrador pode gerenciar este perfil.';
        acoes.appendChild(nota);
      }

      cartao.appendChild(acoes);
    };

    const desenharModoEdicao = () => {
      cartao.innerHTML = '';

      const avisoEdicao = document.createElement('div');
      cartao.appendChild(avisoEdicao);

      // Login somente leitura — nao editavel apos criacao
      const infoLogin = document.createElement('p');
      infoLogin.style.marginBottom = '0.75rem';
      infoLogin.innerHTML = `<strong>${usuario.login}</strong> <span class="texto-suave" style="font-size:0.85rem;">(login não pode ser alterado)</span>`;
      cartao.appendChild(infoLogin);

      // Checkboxes de perfil
      const campoPerfis = document.createElement('div');
      campoPerfis.className = 'campo';
      const labelPerfis = document.createElement('label');
      labelPerfis.textContent = 'Perfis';
      campoPerfis.appendChild(labelPerfis);

      const checkboxRow = document.createElement('div');
      checkboxRow.style.cssText = 'display:flex; gap:1rem; flex-wrap:wrap; margin-top:0.4rem;';

      const perfisDisponiveis = ehAdmin
        ? ['usuario', 'supervisor', 'administrador']
        : ['usuario', 'supervisor'];
      const rotulosPerfis = { usuario: 'Usuário', supervisor: 'Supervisor', administrador: 'Administrador' };

      perfisDisponiveis.forEach((p) => {
        const label = document.createElement('label');
        label.style.cssText = 'display:flex; align-items:center; gap:0.4rem; cursor:pointer; min-height:44px;';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = p;
        cb.checked = usuario.perfis.includes(p);
        label.appendChild(cb);
        label.appendChild(document.createTextNode(rotulosPerfis[p]));
        checkboxRow.appendChild(label);
      });
      campoPerfis.appendChild(checkboxRow);
      cartao.appendChild(campoPerfis);

      // Radio de status
      const campoStatus = document.createElement('div');
      campoStatus.className = 'campo';
      const labelStatus = document.createElement('label');
      labelStatus.textContent = 'Status';
      campoStatus.appendChild(labelStatus);

      const statusRow = document.createElement('div');
      statusRow.style.cssText = 'display:flex; gap:1rem; flex-wrap:wrap; margin-top:0.4rem;';
      ['Ativo', 'Inativo'].forEach((rotulo, idx) => {
        const lab = document.createElement('label');
        lab.style.cssText = 'display:flex; align-items:center; gap:0.4rem; cursor:pointer; min-height:44px;';
        const rb = document.createElement('input');
        rb.type = 'radio';
        rb.name = `ativo-${usuario.id}`;
        rb.value = idx === 0 ? 'true' : 'false';
        rb.checked = idx === 0 ? usuario.ativo : !usuario.ativo;
        lab.appendChild(rb);
        lab.appendChild(document.createTextNode(rotulo));
        statusRow.appendChild(lab);
      });
      campoStatus.appendChild(statusRow);
      cartao.appendChild(campoStatus);

      // Botoes salvar / cancelar
      const acoes = document.createElement('div');
      acoes.className = 'pilha';

      const botaoSalvar = document.createElement('button');
      botaoSalvar.type = 'button';
      botaoSalvar.className = 'botao botao--primaria';
      botaoSalvar.textContent = 'Salvar';
      botaoSalvar.addEventListener('click', async () => {
        const perfisEscolhidos = [...checkboxRow.querySelectorAll('input[type=checkbox]:checked')]
          .map((cb) => cb.value);
        const ativoEscolhido =
          cartao.querySelector(`input[name="ativo-${usuario.id}"]:checked`)?.value === 'true';

        botaoSalvar.disabled = true;
        try {
          const resposta = await RadAuth.requisicaoAutenticada(
            `/usuarios/administrar/${usuario.id}/editar/`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ perfis: perfisEscolhidos, ativo: ativoEscolhido }),
            }
          );
          if (!resposta.ok) {
            const corpo = await resposta.json().catch(() => ({}));
            exibirAviso(avisoEdicao, mensagemDeErro(corpo, 'Não foi possível salvar.'), 'erro');
            return;
          }
          const atualizado = await resposta.json();
          Object.assign(usuario, atualizado); // atualiza objeto em memoria
          desenharModoVisualizacao();
        } catch (e) {
          exibirAviso(avisoEdicao, 'Erro de conexão ao salvar.', 'erro');
        } finally {
          botaoSalvar.disabled = false;
        }
      });
      acoes.appendChild(botaoSalvar);

      const botaoCancelar = document.createElement('button');
      botaoCancelar.type = 'button';
      botaoCancelar.className = 'botao botao--secundaria';
      botaoCancelar.textContent = 'Cancelar';
      botaoCancelar.addEventListener('click', desenharModoVisualizacao);
      acoes.appendChild(botaoCancelar);

      cartao.appendChild(acoes);
    };

    desenharModoVisualizacao();
    return cartao;
  };

  // ---------------------------------------------------------------------------
  // Criar usuario
  // ---------------------------------------------------------------------------

  document.getElementById('botao-criar-usuario').addEventListener('click', async () => {
    avisoCriar.innerHTML = '';
    const login = document.getElementById('campo-novo-login').value.trim();
    const perfis = ['usuario', 'supervisor', 'administrador']
      .filter((p) => document.getElementById(`perfil-novo-${p}`)?.checked);
    const botao = document.getElementById('botao-criar-usuario');

    botao.disabled = true;
    try {
      const resposta = await RadAuth.requisicaoAutenticada('/usuarios/administrar/criar/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login, perfis }),
      });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        exibirAviso(avisoCriar, mensagemDeErro(dados, 'Não foi possível criar o usuário.'), 'erro');
        return;
      }
      exibirAviso(avisoCriar, `Usuário <strong>${dados.login}</strong> criado com sucesso.`, 'sucesso');
      document.getElementById('campo-novo-login').value = '';
      ['usuario', 'supervisor', 'administrador'].forEach((p) => {
        const cb = document.getElementById(`perfil-novo-${p}`);
        if (cb) cb.checked = false;
      });
      todosOsUsuarios.push(dados);
      renderizarLista();
    } catch (e) {
      exibirAviso(avisoCriar, 'Erro de conexão ao criar o usuário.', 'erro');
    } finally {
      botao.disabled = false;
    }
  });

  // ---------------------------------------------------------------------------
  // Modal de exclusao
  // ---------------------------------------------------------------------------

  const modalExcluir = document.getElementById('modal-excluir-usuario');
  let usuarioParaExcluir = null;
  let aoExcluirComSucesso = null;

  const abrirModalExclusao = (usuario, callbackSucesso) => {
    usuarioParaExcluir = usuario;
    aoExcluirComSucesso = callbackSucesso;
    document.getElementById('login-usuario-excluir').textContent = usuario.login;
    modalExcluir.style.display = 'flex';
  };

  document.getElementById('botao-cancelar-exclusao').addEventListener('click', () => {
    modalExcluir.style.display = 'none';
  });

  document.getElementById('botao-confirmar-exclusao').addEventListener('click', async () => {
    if (!usuarioParaExcluir) return;
    const botao = document.getElementById('botao-confirmar-exclusao');
    botao.disabled = true;
    try {
      const resposta = await RadAuth.requisicaoAutenticada(
        `/usuarios/administrar/${usuarioParaExcluir.id}/excluir/`,
        { method: 'POST' }
      );
      modalExcluir.style.display = 'none';
      if (resposta.ok) {
        if (aoExcluirComSucesso) aoExcluirComSucesso();
        exibirAviso(avisoLista, 'Usuário excluído com sucesso.', 'sucesso');
      } else {
        const corpo = await resposta.json().catch(() => ({}));
        exibirAviso(avisoLista, mensagemDeErro(corpo, 'Não foi possível excluir.'), 'erro');
      }
    } catch (e) {
      modalExcluir.style.display = 'none';
      exibirAviso(avisoLista, 'Erro de conexão ao excluir.', 'erro');
    } finally {
      botao.disabled = false;
    }
  });

  // ---------------------------------------------------------------------------
  // Inicializar
  // ---------------------------------------------------------------------------

  await carregarLista();
});
