const fs = require('fs');
const path = require('path');
let codigo = fs.readFileSync(
  path.join(__dirname, '..', 'static', 'interface', 'js', 'regras_horario.js'),
  'utf8'
);
codigo = codigo.replace('const RegrasHorario', 'global.RegrasHorario');
eval(codigo);

let falhas = 0;
function assert(condicao, mensagem) {
  if (!condicao) {
    console.error('FALHOU:', mensagem);
    falhas++;
  } else {
    console.log('OK:', mensagem);
  }
}

const dataInicio = '2026-06-15';
const horaInicio = '22:00';
const horaTermino = '02:00';
const dataTermino = RegrasHorario.ajustarDataPorViradaDeMeiaNoite(dataInicio, horaInicio, horaTermino);
assert(dataTermino === '2026-06-16', 'virada de meia-noite calcula 16/06');

const dtInicio = RegrasHorario.montarDataHora(dataInicio, horaInicio);
const dtTermino = RegrasHorario.montarDataHora(dataTermino, horaTermino);
const duracaoMin = RegrasHorario.calcularDuracaoMinutos(dtInicio, dtTermino);
assert(duracaoMin === 240, `duracao = 240 min (exemplo oficial EFD), veio ${duracaoMin}`);
assert(RegrasHorario.formatarDuracao(duracaoMin) === '4h00', `formatarDuracao = "4h00", veio "${RegrasHorario.formatarDuracao(duracaoMin)}"`);

assert(RegrasHorario.ajustarDataPorViradaDeMeiaNoite('2026-06-15', '08:00', '12:00') === '2026-06-15', 'sem virada quando termino > inicio');

const d1 = RegrasHorario.montarDataHora('2026-06-15', '08:00');
const d2 = RegrasHorario.montarDataHora('2026-06-15', '12:00');
assert(RegrasHorario.calcularDuracaoMinutos(d1, d2) === 240, 'duracao simples 08:00-12:00 = 240min');
assert(RegrasHorario.formatarDuracao(270) === '4h30', 'formatarDuracao(270) = "4h30"');

const prog = RegrasHorario.montarDataHora('2026-06-15', '08:00');
const real10 = RegrasHorario.montarDataHora('2026-06-15', '08:10');
const real11 = RegrasHorario.montarDataHora('2026-06-15', '08:11');
assert(RegrasHorario.calcularAtrasoInicio(prog, real10) === false, 'atraso inicio: 10min exatos NAO conta');
assert(RegrasHorario.calcularAtrasoInicio(prog, real11) === true, 'atraso inicio: 11min conta como atraso');

const progTermino = RegrasHorario.montarDataHora('2026-06-15', '12:00');
const realTermino1min = RegrasHorario.montarDataHora('2026-06-15', '12:01');
const realTerminoExato = RegrasHorario.montarDataHora('2026-06-15', '12:00');
assert(RegrasHorario.calcularAtrasoTermino(progTermino, realTermino1min) === true, 'atraso termino: 1min ja conta (sem tolerancia)');
assert(RegrasHorario.calcularAtrasoTermino(progTermino, realTerminoExato) === false, 'atraso termino: no horario exato nao conta');

console.log(`\n${falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' TESTE(S) FALHARAM'}`);
process.exit(falhas === 0 ? 0 : 1);
