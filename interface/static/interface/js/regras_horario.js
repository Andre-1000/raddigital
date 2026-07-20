/*
 * RegrasHorario — espelho client-side de rad/regras_horario.py.
 *
 * Mesma logica pura do backend (RG-HOR-001 a 027), reescrita em JS
 * para o formulario poder mostrar duracao e atraso calculados em
 * tempo real, offline, sem depender do servidor. O calculo definitivo
 * continua sendo feito no backend na hora da sincronizacao -- este
 * modulo e so para feedback imediato ao usuario durante o preenchimento.
 *
 * Mantido deliberadamente com a mesma forma do modulo Python (mesmos
 * nomes de funcao, mesma sequencia de passos) para que uma mudanca de
 * regra de negocio seja facil de replicar dos dois lados.
 */
const RegrasHorario = (function () {
  const TOLERANCIA_ATRASO_INICIO_MIN = 10;

  /** 'HH:MM' -> minutos desde 00:00. */
  function horaParaMinutos(horaTexto) {
    const [h, m] = horaTexto.split(':').map(Number);
    return h * 60 + m;
  }

  /**
   * RG-HOR-021/022: quando a hora de termino e menor que a hora de
   * inicio, a data de termino sugerida e data_inicio + 1 dia.
   */
  function ajustarDataPorViradaDeMeiaNoite(dataInicioIso, horaInicio, horaTermino) {
    if (!horaInicio || !horaTermino) return dataInicioIso;
    if (horaParaMinutos(horaTermino) < horaParaMinutos(horaInicio)) {
      const data = new Date(dataInicioIso + 'T00:00:00');
      data.setDate(data.getDate() + 1);
      return data.toISOString().slice(0, 10);
    }
    return dataInicioIso;
  }

  /** data 'YYYY-MM-DD' + hora 'HH:MM' -> objeto Date completo. */
  function montarDataHora(dataIso, horaTexto) {
    return new Date(`${dataIso}T${horaTexto}:00`);
  }

  /** RG-HOR-004/005/026/027: duracao em minutos usando data+hora completos. */
  function calcularDuracaoMinutos(dataHoraInicio, dataHoraTermino) {
    return Math.round((dataHoraTermino.getTime() - dataHoraInicio.getTime()) / 60000);
  }

  /** Formata minutos como "4h00", "4h30" (mesmo formato dos exemplos da EFD). */
  function formatarDuracao(minutosTotais) {
    if (minutosTotais == null || isNaN(minutosTotais)) return '--';
    const horas = Math.floor(minutosTotais / 60);
    const minutos = minutosTotais % 60;
    return `${horas}h${String(minutos).padStart(2, '0')}`;
  }

  /** RG-HOR-009/010: atraso no inicio, com tolerancia de 10 minutos. */
  function calcularAtrasoInicio(dataHoraProgInicio, dataHoraRealInicio) {
    const diferencaMin = (dataHoraRealInicio.getTime() - dataHoraProgInicio.getTime()) / 60000;
    return diferencaMin > TOLERANCIA_ATRASO_INICIO_MIN;
  }

  /** RG-HOR-011/012: atraso no termino, sem tolerancia. */
  function calcularAtrasoTermino(dataHoraProgTermino, dataHoraRealTermino) {
    return dataHoraRealTermino.getTime() > dataHoraProgTermino.getTime();
  }

  return {
    ajustarDataPorViradaDeMeiaNoite,
    montarDataHora,
    calcularDuracaoMinutos,
    formatarDuracao,
    calcularAtrasoInicio,
    calcularAtrasoTermino,
  };
})();
