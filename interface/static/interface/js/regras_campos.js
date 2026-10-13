/*
 * RegrasCampos — avisa o usuario, NA HORA e logo abaixo do proprio campo,
 * quando o que foi digitado nao segue a regra do campo (30/09/2026).
 *
 * Por que existe: antes, quem passava do limite de uma regra so
 * descobria depois de clicar em Sincronizar (e, em alguns casos, nem
 * isso: um numero de OS grande demais virou um "Erro inesperado"
 * generico). Alem disso, varios campos corrigiam o texto em silencio --
 * o N° SA, por exemplo, apagava qualquer letra sem dizer nada, e o
 * Km/Poste parava de aceitar digitos no meio da digitacao.
 *
 * Dois tipos de aviso:
 *   - PERSISTENTE: a regra e violada e o valor continua errado ate a
 *     pessoa corrigir (ex.: OS com 12 digitos). O aviso fica na tela
 *     enquanto durar, e bloqueia a sincronizacao (ver
 *     violacoesAtuais) -- o servidor recusaria de qualquer jeito, e
 *     mandar o RAD com todas as fotos so pra levar um "nao" gasta
 *     internet do celular em campo e processamento do servidor.
 *   - TEMPORARIO: o campo corrige o texto sozinho (letra apagada,
 *     digito a mais cortado) e o aviso so explica o que aconteceu,
 *     sumindo depois de alguns segundos.
 *
 * AS REGRAS DAQUI ESPELHAM rad/validadores.py. O servidor continua
 * sendo a palavra final (ele valida tudo de novo na sincronizacao); este
 * arquivo so adianta o aviso. Para os limites numericos nao divergirem
 * sem ninguem perceber, rad/test_regras_campos_consistencia.py compara
 * as constantes abaixo com as do Python e falha se forem diferentes.
 */
const RegrasCampos = (function () {
  // ---- Limites (espelham rad/validadores.py) ------------------------------
  const LIMITE_DIGITOS_OS = 11;
  const LIMITE_CARACTERES_RESPONSAVEL = 50;
  const LIMITE_VALOR_OS = Math.pow(10, LIMITE_DIGITOS_OS) - 1;

  const MS_AVISO_TEMPORARIO = 5000;

  // ---- Regras puras: recebem o texto, devolvem a mensagem ou null ---------

  function verificarOs(texto) {
    const valor = String(texto == null ? '' : texto).trim();
    if (valor === '') return null; // vazio: quem cobra e a regra de "obrigatorio"

    const numero = Number(valor);
    if (!Number.isFinite(numero) || !Number.isInteger(numero) || numero <= 0) {
      return 'A OS deve ser um número inteiro maior que zero.';
    }
    if (numero > LIMITE_VALOR_OS) {
      let mensagem = `A OS deve ter no máximo ${LIMITE_DIGITOS_OS} dígitos.`;
      if (/^\d+$/.test(valor)) {
        const digitos = valor.replace(/^0+/, '').length;
        mensagem += ` Você digitou ${digitos}.`;
      }
      return mensagem;
    }
    return null;
  }

  function verificarResponsavel(texto) {
    const valor = String(texto == null ? '' : texto);
    if (valor.length > LIMITE_CARACTERES_RESPONSAVEL) {
      return (
        `O Responsável Atividade deve ter no máximo ${LIMITE_CARACTERES_RESPONSAVEL} caracteres. ` +
        `Você digitou ${valor.length}.`
      );
    }
    return null;
  }

  /*
   * Data da Atividade, no formato DD/MM/AAAA. opcoes.aoDigitar = true
   * nao reclama de data ainda incompleta (a pessoa esta no meio da
   * digitacao); opcoes.hoje permite fixar "hoje" nos testes. A
   * comparacao e com a data LOCAL do aparelho (mesmo criterio do
   * servidor, que usa a data de Sao Paulo -- VLD-046).
   */
  function verificarDataAtividade(textoBr, opcoes) {
    const aoDigitar = !!(opcoes && opcoes.aoDigitar);
    const hoje = (opcoes && opcoes.hoje) || new Date();

    const texto = String(textoBr == null ? '' : textoBr).trim();
    if (texto === '') return null;

    if (!/^\d{2}\/\d{2}\/\d{4}$/.test(texto)) {
      return aoDigitar ? null : 'Informe a Data da Atividade completa, no formato DD/MM/AAAA.';
    }

    const [dia, mes, ano] = texto.split('/').map(Number);
    const data = new Date(ano, mes - 1, dia);
    if (data.getFullYear() !== ano || data.getMonth() !== mes - 1 || data.getDate() !== dia) {
      return 'A Data da Atividade informada não existe. Use DD/MM/AAAA com uma data real.';
    }

    const inicioDeHoje = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
    if (data > inicioDeHoje) {
      return 'A Data da Atividade não pode ser posterior a hoje.';
    }
    return null;
  }

  // ---- Avisos na tela -------------------------------------------------------

  const avisos = new WeakMap(); // campo -> <p> do aviso
  const temporizadores = new WeakMap(); // campo -> id do setTimeout
  let contadorDeAvisos = 0;

  function elementoDoAviso(campo, ancora) {
    let aviso = avisos.get(campo);
    if (!aviso) {
      contadorDeAvisos += 1;
      aviso = campo.ownerDocument.createElement('p');
      aviso.className = 'campo__erro';
      aviso.id = `aviso-regra-${campo.id || 'campo'}-${contadorDeAvisos}`;
      aviso.setAttribute('role', 'alert');
      aviso.hidden = true;
      // "ancora" existe para campos que vivem dentro de uma linha
      // (ex.: Data da Atividade, com o botao de calendario ao lado) --
      // o aviso entra DEPOIS da linha inteira, nao no meio dela.
      (ancora || campo).insertAdjacentElement('afterend', aviso);
      avisos.set(campo, aviso);
    }
    return aviso;
  }

  function mostrarRegra(campo, mensagem, opcoes) {
    const aviso = elementoDoAviso(campo, opcoes && opcoes.ancora);
    aviso.textContent = mensagem;
    aviso.hidden = false;
    campo.setAttribute('aria-invalid', 'true');
    campo.setAttribute('aria-describedby', aviso.id);

    clearTimeout(temporizadores.get(campo));
    if (opcoes && opcoes.temporario) {
      temporizadores.set(
        campo,
        setTimeout(function () {
          limparRegra(campo);
        }, MS_AVISO_TEMPORARIO)
      );
    }
  }

  function limparRegra(campo) {
    clearTimeout(temporizadores.get(campo));
    const aviso = avisos.get(campo);
    if (aviso) aviso.hidden = true;
    campo.removeAttribute('aria-invalid');
    campo.removeAttribute('aria-describedby');
  }

  // ---- Campos que corrigem o texto sozinhos (aviso temporario) --------------

  /*
   * Aceita so numeros, ate `maximo` digitos. Devolve o texto ja
   * corrigido e, se algo foi descartado, explica por que.
   */
  function somenteDigitos(campo, opcoes) {
    const bruto = campo.value;
    const digitos = bruto.replace(/\D/g, '');
    if (digitos.length !== bruto.length) {
      mostrarRegra(campo, `${opcoes.rotulo} aceita apenas números.`, { temporario: true });
    } else if (digitos.length > opcoes.maximo) {
      mostrarRegra(campo, `${opcoes.rotulo} aceita no máximo ${opcoes.maximo} dígitos.`, {
        temporario: true,
      });
    } else {
      limparRegra(campo);
    }
    return digitos.slice(0, opcoes.maximo);
  }

  /*
   * Campos com mascara (Km/Poste: XX/XX + XXX). As barras e o "+" entram
   * sozinhos -- o aviso so aparece quando a pessoa digita algo que a
   * mascara descarta (uma letra, um digito alem do limite).
   */
  function mascararComAviso(campo, aplicarMascara, opcoes) {
    const bruto = campo.value;
    if (/[^\d\/+\s]/.test(bruto)) {
      mostrarRegra(
        campo,
        `${opcoes.rotulo} aceita apenas números — as barras e o + entram sozinhos (${opcoes.formato}).`,
        { temporario: true }
      );
    } else if (bruto.replace(/\D/g, '').length > opcoes.maximoDigitos) {
      mostrarRegra(
        campo,
        `${opcoes.rotulo} aceita no máximo ${opcoes.maximoDigitos} números (${opcoes.formato}).`,
        { temporario: true }
      );
    } else {
      limparRegra(campo);
    }
    campo.value = aplicarMascara(bruto);
  }

  /*
   * Aviso de limite de caracteres para QUALQUER campo com maxlength: o
   * navegador simplesmente para de aceitar texto no limite, sem dizer
   * nada. Este ouvinte unico (instalado no formulario inteiro, entao
   * vale tambem para campos criados depois) mostra o motivo quando a
   * pessoa tenta digitar ou colar alem do limite. Um campo pode trazer
   * uma mensagem propria em data-mensagem-limite.
   */
  // Tipos de digitacao em que da pra saber com precisao quanto texto
  // esta entrando. Fica de fora a "composicao" (insertCompositionText),
  // usada por teclados de celular com sugestao de palavras: ali o evento
  // traz a palavra INTEIRA em formacao, que ja esta contada no valor do
  // campo, e a conta daria aviso falso perto do limite.
  const TIPOS_DE_ENTRADA_MEDIVEIS = [
    'insertText',
    'insertFromPaste',
    'insertFromDrop',
    'insertReplacementText',
    'insertLineBreak',
    'insertParagraph',
  ];

  function instalarAvisoDeLimite(raiz) {
    raiz.addEventListener('beforeinput', function (evento) {
      const campo = evento.target;
      if (!campo || !campo.maxLength || campo.maxLength < 0) return;
      if (TIPOS_DE_ENTRADA_MEDIVEIS.indexOf(evento.inputType) === -1) return;

      let texto = evento.data;
      if (texto == null && evento.dataTransfer) texto = evento.dataTransfer.getData('text');
      if (texto == null && /^insert(LineBreak|Paragraph)$/.test(evento.inputType)) texto = '\n';
      texto = texto || '';

      const selecionado = (campo.selectionEnd || 0) - (campo.selectionStart || 0);
      if (campo.value.length - selecionado + texto.length > campo.maxLength) {
        const mensagem =
          (campo.dataset && campo.dataset.mensagemLimite) ||
          `Limite de ${campo.maxLength} caracteres atingido.`;
        mostrarRegra(campo, mensagem, { temporario: true });
      }
    });
  }

  // ---- Regras persistentes: avaliam, mostram e bloqueiam o envio -----------

  const instaladas = [];

  function estaVisivel(campo) {
    // Campo escondido (desabilitado em Configuracoes, por exemplo) nao
    // conta: o servidor tambem ignora os erros de campo desabilitado.
    for (let no = campo; no && no.nodeType === 1; no = no.parentElement) {
      if (no.hidden || (no.style && no.style.display === 'none')) return false;
    }
    return true;
  }

  function instalarRegra(definicao) {
    const regra = {
      campo: definicao.campo,
      verificar: definicao.verificar,
      ancora: definicao.ancora,
      avaliar: function (aoDigitar) {
        const mensagem = regra.verificar(regra.campo.value, { aoDigitar: !!aoDigitar });
        if (mensagem) {
          mostrarRegra(regra.campo, mensagem, { ancora: regra.ancora });
        } else {
          limparRegra(regra.campo);
        }
        return mensagem;
      },
    };
    regra.campo.addEventListener('input', function () {
      regra.avaliar(true);
    });
    regra.campo.addEventListener('blur', function () {
      regra.avaliar(false);
    });
    instaladas.push(regra);
    return regra;
  }

  // Reavalia um campo cujo valor foi mudado por codigo (sem evento de
  // digitacao), ex.: nome escolhido na lista de sugestoes.
  function reavaliar(campo) {
    instaladas.forEach(function (regra) {
      if (regra.campo === campo) regra.avaliar(false);
    });
  }

  function reavaliarTodas() {
    instaladas.forEach(function (regra) {
      regra.avaliar(false);
    });
  }

  // Lista [{campo, mensagem}] dos campos VISIVEIS que violam a regra agora.
  function violacoesAtuais() {
    const violacoes = [];
    instaladas.forEach(function (regra) {
      if (!estaVisivel(regra.campo)) return;
      const mensagem = regra.avaliar(false);
      if (mensagem) violacoes.push({ campo: regra.campo, mensagem: mensagem });
    });
    return violacoes;
  }

  return {
    LIMITE_DIGITOS_OS,
    LIMITE_CARACTERES_RESPONSAVEL,
    verificarOs,
    verificarResponsavel,
    verificarDataAtividade,
    mostrarRegra,
    limparRegra,
    somenteDigitos,
    mascararComAviso,
    instalarAvisoDeLimite,
    instalarRegra,
    reavaliar,
    reavaliarTodas,
    violacoesAtuais,
  };
})();
