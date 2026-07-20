/*
 * ValidadoresArquivos — espelho client-side de
 * rad/validadores_arquivos.py. Mesmos limites (RG-ANX-003/004/005),
 * mesma filosofia: valida o CONTEUDO do arquivo, nao so o nome/extensao.
 *
 * Fotos: tenta decodificar de verdade com createImageBitmap() (nativo
 * do navegador) -- equivalente ao Image.open(...).verify() do Pillow
 * no backend. Um arquivo renomeado para .jpg mas com conteudo invalido
 * falha aqui, antes de gastar dados enviando algo que o servidor vai
 * rejeitar de qualquer forma.
 *
 * PDF: checa a assinatura magica "%PDF" no inicio do arquivo. Mais
 * simples que o parse completo do pypdf no backend (que e quem faz a
 * validacao definitiva), mas pega o caso mais comum -- arquivo errado
 * selecionado por engano -- sem depender de nenhuma biblioteca extra
 * no navegador.
 */
const ValidadoresArquivos = (function () {
  const LIMITE_TAMANHO_BYTES = 10 * 1024 * 1024; // 10MB
  const LIMITE_FOTOS_POR_CATEGORIA = 2;
  const LIMITE_PDF = 1;

  function validarTamanho(arquivo) {
    if (arquivo.size > LIMITE_TAMANHO_BYTES) {
      return `O arquivo "${arquivo.name}" excede o limite de 10MB.`;
    }
    return null;
  }

  /** Retorna null se valida, ou uma mensagem de erro. */
  async function validarFoto(arquivo) {
    const erroTamanho = validarTamanho(arquivo);
    if (erroTamanho) return erroTamanho;

    try {
      const bitmap = await createImageBitmap(arquivo);
      bitmap.close();
      return null;
    } catch (erro) {
      return `O arquivo "${arquivo.name}" não é uma foto válida ou está corrompido.`;
    }
  }

  function lerPrimeirosBytes(arquivo, quantidade) {
    return new Promise((resolve, reject) => {
      const leitor = new FileReader();
      leitor.onload = () => resolve(new Uint8Array(leitor.result));
      leitor.onerror = () => reject(leitor.error);
      leitor.readAsArrayBuffer(arquivo.slice(0, quantidade));
    });
  }

  async function validarPdf(arquivo) {
    const erroTamanho = validarTamanho(arquivo);
    if (erroTamanho) return erroTamanho;

    try {
      const bytes = await lerPrimeirosBytes(arquivo, 5);
      const assinatura = String.fromCharCode(...bytes);
      if (!assinatura.startsWith('%PDF')) {
        return `O arquivo "${arquivo.name}" não é um PDF válido ou está corrompido.`;
      }
      return null;
    } catch (erro) {
      return `Não foi possível ler o arquivo "${arquivo.name}".`;
    }
  }

  return {
    LIMITE_TAMANHO_BYTES,
    LIMITE_FOTOS_POR_CATEGORIA,
    LIMITE_PDF,
    validarFoto,
    validarPdf,
  };
})();
