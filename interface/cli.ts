/**
 * Interface de Linha de Comando - EVE
 */

import { Eve } from '../núcleo/index.js';

const eve = new Eve();

async function main() {
  const args = process.argv.slice(2);
  const comando = args[0] || 'status';

  await eve.inicializar();

  switch (comando) {
    case 'status':
      await mostrarStatus();
      break;
    case 'memória':
      await consultarMemória(args[1]);
      break;
    case 'evoluir':
      await evoluir();
      break;
    case 'ciclo':
      await executarCiclo();
      break;
    default:
      console.log('Comandos: status, memória <query>, evoluir, ciclo');
  }
}

async function mostrarStatus() {
  const estado = eve.getEstado();
  console.log('\n🌙 EVE Status');
  console.log('══════════════');
  console.log(`Ciclo:        #${estado.ciclo}`);
  console.log(`Idade:        ${estado.idade} dias`);
  console.log(`Dataset:      ${estado.dataset.toLocaleString()} pares`);
  console.log(`Scripts:      ${estado.scripts}`);
  console.log(`Atratores:    ${estado.atratores}/17`);
  console.log('');
}

async function consultarMemória(query?: string) {
  if (!query) {
    console.log('Uso: eve memória <query>');
    return;
  }
  const cacm = eve.getCACM();
  const memórias = await cacm.canalDinâmico(query);
  console.log(`\n🔍 Memórias sobre: ${query}`);
  console.log('═══════════════════════════════════════');
  memórias.forEach(m => {
    console.log(`[${new Date(m.timestamp).toLocaleString()}] ${m.conteúdo}`);
  });
}

async function evoluir() {
  const ad = eve.getAutoDream();
  console.log('\n🔄 Executando autoDream...');
  const resultado = ad.evoluir('evolução manual');
  console.log(`Insight: ${resultado.insight.conteúdo}`);
  console.log(`Aplicar: ${resultado.aplicação ? 'Sim' : 'Não'}`);
}

async function executarCiclo() {
  console.log('\n⚡ Executando ciclo...');
  await eve.ciclo();
  console.log('Ciclo completo.\n');
}

main().catch(console.error);
