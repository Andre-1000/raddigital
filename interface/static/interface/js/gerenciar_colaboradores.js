/*
 * Gerenciar Colaboradores — exclusivo do Administrador (RG-RESP-012).
 *
 * Ao contrario do resto do app, esta tela nao precisa funcionar
 * offline: e uma tela administrativa, batendo direto na API a cada
 * acao (RG-RESP-002/003/008/011/012 sao regras do backend, ja
 * cobertas la; aqui e so a interface).
 */
document.addEventListener('DOMContentLoaded', async function () {
  if (!RadAuth.exigirSessao()) return;
  if (!RadAuth.temPerfil('administrador')) {
    window.location.href = '/inicio/';
    return;
  }
  document.getElementById('conteudo-protegido').style.display = '';

  const listaEl = document.getElementById('lista-colaboradores');
  const avisoLista = document.getElementById('aviso-lista');
  const avisoCriar = document.getElementById('aviso-criar');

  function mensagemDeErro(corpo, padrao) {
    if (corpo && Array.isArray(corpo.erros) && corpo.erros.length) {
      return corpo.erros.map((e) => e.mensagem).join(' ');
    }
    if (corpo && corpo.erro) return corpo.erro;
    return padrao;
  }

  // ---- Listagem ------------------------------------------------------

  async function carregarLista() {
    avisoLista.innerHTML = '';
    listaEl.innerHTML = '';
    try {
      const resposta = await RadAuth.requisicaoAutenticada('/colaboradores/administrar/');
      if (!resposta.ok) {
        avisoLista.innerHTML = '<div class="aviso aviso--erro">Não foi possível carregar os colaboradores.</div>';
        return;
      }
      const dados = await resposta.json();
      if (dados.colaboradores.length === 0) {
        const vazio = document.createElement('p');
        vazio.className = 'texto-suave centro';
        vazio.textContent = 'Nenhum colaborador cadastrado ainda.';
        listaEl.appendChild(vazio);
        return;
      }
      dados.colaboradores.forEach(renderizarLinha);
    } catch (erro) {
      avisoLista.innerHTML = '<div class="aviso aviso--erro">Erro de conexão ao carregar os colaboradores.</div>';
    }
  }

  function renderizarLinha(colaborador) {
    const cartao = document.createElement('div');
    cartao.className = 'cartao';
    cartao.dataset.id = colaborador.id;

    function desenharModoVisualizacao() {
      cartao.innerHTML = '';

      const topo = document.createElement('div');
      topo.style.display = 'flex';
      topo.style.justifyContent = 'space-between';
      topo.style.alignItems = 'center';
      topo.innerHTML = `
        <div>
          <strong>${colaborador.nome}</strong>
          <div class="texto-suave" style="font-size:0.85rem;">Registro ${colaborador.registro_empresa}</div>
        </div>
        <span class="selo ${colaborador.ativo ? 'selo--online' : 'selo--offline'}">${colaborador.ativo ? 'Ativo' : 'Inativo'}</span>
      `;
      cartao.appendChild(topo);

      const avisoLinha = document.createElement('div');
      cartao.appendChild(avisoLinha);

      const acoes = document.createElement('div');
      acoes.className = 'pilha';
      acoes.style.marginTop = '0.75rem';

      const botaoEditar = document.createElement('button');
      botaoEditar.type = 'button';
      botaoEditar.className = 'botao botao--secundaria';
      botaoEditar.textContent = 'Editar';
      botaoEditar.addEventListener('click', desenharModoEdicao);
      acoes.appendChild(botaoEditar);

      const botaoToggle = document.createElement('button');
      botaoToggle.type = 'button';
      botaoToggle.className = 'botao botao--secundaria';
      botaoToggle.textContent = colaborador.ativo ? 'Desativar' : 'Ativar';
      botaoToggle.addEventListener('click', async function () {
        botaoToggle.disabled = true;
        try {
          const resposta = await RadAuth.requisicaoAutenticada(`/colaboradores/${colaborador.id}/editar/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ativo: !colaborador.ativo }),
          });
          if (!resposta.ok) {
            const corpo = await resposta.json().catch(() => ({}));
            avisoLinha.innerHTML = `<div class="aviso aviso--erro">${mensagemDeErro(corpo, 'Não foi possível atualizar.')}</div>`;
            botaoToggle.disabled = false;
            return;
          }
          const atualizado = await resposta.json();
          colaborador.ativo = atualizado.ativo;
          desenharModoVisualizacao();
        } catch (erro) {
          avisoLinha.innerHTML = '<div class="aviso aviso--erro">Erro de conexão.</div>';
          botaoToggle.disabled = false;
        }
      });
      acoes.appendChild(botaoToggle);

      const botaoExcluir = document.createElement('button');
      botaoExcluir.type = 'button';
      botaoExcluir.className = 'botao botao--perigo';
      botaoExcluir.textContent = 'Excluir';
      botaoExcluir.addEventListener('click', function () {
        abrirModalExclusao(colaborador, function () {
          cartao.remove();
        });
      });
      acoes.appendChild(botaoExcluir);

      cartao.appendChild(acoes);
    }

    function desenharModoEdicao() {
      cartao.innerHTML = '';

      const avisoEdicao = document.createElement('div');
      cartao.appendChild(avisoEdicao);

      const campoRegistro = document.createElement('div');
      campoRegistro.className = 'campo';
      campoRegistro.innerHTML = `
        <label>Registro da Empresa</label>
        <input type="text" inputmode="numeric" maxlength="20" value="${colaborador.registro_empresa}">
      `;
      cartao.appendChild(campoRegistro);

      const campoNome = document.createElement('div');
      campoNome.className = 'campo';
      campoNome.innerHTML = `
        <label>Nome</label>
        <input type="text" maxlength="200" value="${colaborador.nome}">
      `;
      cartao.appendChild(campoNome);

      const acoes = document.createElement('div');
      acoes.className = 'pilha';

      const botaoSalvar = document.createElement('button');
      botaoSalvar.type = 'button';
      botaoSalvar.className = 'botao botao--primaria';
      botaoSalvar.textContent = 'Salvar';
      botaoSalvar.addEventListener('click', async function () {
        const novoRegistro = campoRegistro.querySelector('input').value.replace(/\D/g, '');
        const novoNome = campoNome.querySelector('input').value.trim();

        botaoSalvar.disabled = true;
        try {
          const resposta = await RadAuth.requisicaoAutenticada(`/colaboradores/${colaborador.id}/editar/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ registro_empresa: novoRegistro, nome: novoNome }),
          });
          if (!resposta.ok) {
            const corpo = await resposta.json().catch(() => ({}));
            avisoEdicao.innerHTML = `<div class="aviso aviso--erro">${mensagemDeErro(corpo, 'Não foi possível salvar.')}</div>`;
            botaoSalvar.disabled = false;
            return;
          }
          const atualizado = await resposta.json();
          colaborador.registro_empresa = atualizado.registro_empresa;
          colaborador.nome = atualizado.nome;
          desenharModoVisualizacao();
        } catch (erro) {
          avisoEdicao.innerHTML = '<div class="aviso aviso--erro">Erro de conexão.</div>';
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
    }

    desenharModoVisualizacao();
    listaEl.appendChild(cartao);
  }

  await carregarLista();

  // ---- Adicionar -------------------------------------------------------

  document.getElementById('botao-adicionar').addEventListener('click', async function () {
    avisoCriar.innerHTML = '';
    const campoRegistro = document.getElementById('campo-novo-registro');
    const campoNome = document.getElementById('campo-novo-nome');
    const registro = campoRegistro.value.replace(/\D/g, '');
    const nome = campoNome.value.trim();

    const botao = document.getElementById('botao-adicionar');
    botao.disabled = true;
    try {
      const resposta = await RadAuth.requisicaoAutenticada('/colaboradores/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ registro_empresa: registro, nome: nome }),
      });
      if (!resposta.ok) {
        const corpo = await resposta.json().catch(() => ({}));
        avisoCriar.innerHTML = `<div class="aviso aviso--erro">${mensagemDeErro(corpo, 'Não foi possível adicionar.')}</div>`;
        return;
      }
      campoRegistro.value = '';
      campoNome.value = '';
      avisoCriar.innerHTML = '<div class="aviso aviso--sucesso">Colaborador adicionado.</div>';
      await carregarLista();
    } catch (erro) {
      avisoCriar.innerHTML = '<div class="aviso aviso--erro">Erro de conexão.</div>';
    } finally {
      botao.disabled = false;
    }
  });

  // ---- Importar CSV -------------------------------------------------------

  const avisoImportar = document.getElementById('aviso-importar');

  function montarResumoImportacao(corpo) {
    const partes = [`<strong>${corpo.criados}</strong> adicionado(s)`, `<strong>${corpo.atualizados}</strong> atualizado(s)`];
    let html = `<div class="aviso aviso--sucesso">${partes.join(', ')}.</div>`;

    if (corpo.erros && corpo.erros.length > 0) {
      const itensErro = corpo.erros
        .map((e) => `<li>Linha ${e.linha}: ${e.mensagem}</li>`)
        .join('');
      html += `
        <div class="aviso aviso--atencao">
          <strong>${corpo.erros.length} linha(s) não importada(s):</strong>
          <ul style="margin: 0.5rem 0 0; padding-left: 1.2rem;">${itensErro}</ul>
        </div>
      `;
    }
    return html;
  }

  document.getElementById('botao-importar').addEventListener('click', async function () {
    avisoImportar.innerHTML = '';
    const campoArquivo = document.getElementById('campo-arquivo-importar');
    const arquivo = campoArquivo.files[0];
    if (!arquivo) {
      avisoImportar.innerHTML = '<div class="aviso aviso--erro">Escolha um arquivo CSV.</div>';
      return;
    }

    const botao = document.getElementById('botao-importar');
    botao.disabled = true;
    botao.textContent = 'Importando…';
    try {
      const formData = new FormData();
      formData.append('arquivo', arquivo);

      const resposta = await RadAuth.requisicaoAutenticada('/colaboradores/importar/', {
        method: 'POST',
        body: formData,
      });
      const corpo = await resposta.json().catch(() => ({}));

      if (!resposta.ok) {
        avisoImportar.innerHTML = `<div class="aviso aviso--erro">${corpo.erro || 'Não foi possível importar o arquivo.'}</div>`;
        return;
      }

      avisoImportar.innerHTML = montarResumoImportacao(corpo);
      campoArquivo.value = '';
      await carregarLista();
    } catch (erro) {
      avisoImportar.innerHTML = '<div class="aviso aviso--erro">Erro de conexão ao importar.</div>';
    } finally {
      botao.disabled = false;
      botao.textContent = 'Importar';
    }
  });

  // ---- Exclusao ----------------------------------------------------------

  const modalExcluir = document.getElementById('modal-excluir-colaborador');
  let colaboradorParaExcluir = null;
  let aoExcluirComSucesso = null;

  function abrirModalExclusao(colaborador, callbackSucesso) {
    colaboradorParaExcluir = colaborador;
    aoExcluirComSucesso = callbackSucesso;
    document.getElementById('nome-colaborador-excluir').textContent = colaborador.nome;
    modalExcluir.style.display = 'flex';
  }

  document.getElementById('botao-cancelar-exclusao-colaborador').addEventListener('click', function () {
    modalExcluir.style.display = 'none';
  });

  document.getElementById('botao-confirmar-exclusao-colaborador').addEventListener('click', async function () {
    if (!colaboradorParaExcluir) return;
    const botao = document.getElementById('botao-confirmar-exclusao-colaborador');
    botao.disabled = true;
    try {
      const resposta = await RadAuth.requisicaoAutenticada(
        `/colaboradores/${colaboradorParaExcluir.id}/excluir/`,
        { method: 'POST' }
      );
      if (resposta.ok) {
        modalExcluir.style.display = 'none';
        if (aoExcluirComSucesso) aoExcluirComSucesso();
      } else {
        modalExcluir.style.display = 'none';
        avisoLista.innerHTML = '<div class="aviso aviso--erro">Não foi possível excluir.</div>';
      }
    } catch (erro) {
      modalExcluir.style.display = 'none';
      avisoLista.innerHTML = '<div class="aviso aviso--erro">Erro de conexão ao excluir.</div>';
    } finally {
      botao.disabled = false;
    }
  });
});
