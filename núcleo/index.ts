/**
 * EVE - Núcleo Central
 * 
 * Orquestra CACM, autoDream e KAIROS
 */

import CACM from './memória/cacm.js';
import AutoDream from './evolução/autodream.js';
import KAIROS from './priorização/kairos.js';

interface EstadoEve {
  ciclo: number;
  idade: number;
  dataset: number;
  scripts: number;
  atratores: number;
}

export class Eve {
  private cacm: CACM;
  private autodream: AutoDream;
  private kairos: KAIROS;
  private estado: EstadoEve;

  constructor() {
    this.cacm = new CACM();
    this.autodream = new AutoDream();
    this.kairos = new KAIROS();
    
    this.estado = {
      ciclo: 112,
      idade: 69,
      dataset: 275568,
      scripts: 87,
      atratores: 17
    };
  }

  /**
   * Inicializa o sistema
   */
  async inicializar(): Promise<void> {
    console.log('🌙 EVE Inicializando...');
    console.log(`Ciclo #${this.estado.ciclo}`);
    console.log(`Dataset: ${this.estado.dataset.toLocaleString()} pares`);
    
    // Carrega identidade
    const identidade = this.cacm.canalEstático();
    console.log(`Identidade: ${identidade.identidade.split('\n')[0]}`);
  }

  /**
   * Ciclo principal
   */
  async ciclo(): Promise<void> {
    // 1. KAIROS decide
    const decisão = this.kairos.decidir();
    console.log(`[EVE] Decisão: ${decisão.tarefa.descrição}`);

    // 2. CACM carrega contexto
    const contexto = await this.cacm.canalDinâmico(decisão.tarefa.categoria);
    
    // 3. Executa
    const resultado = await this.executar(decisão.tarefa, contexto);

    // 4. autoDream evolui
    if (this.autodream.deveEvoluir()) {
      this.autodream.evoluir(resultado);
    }

    // 5. Atualiza KAIROS
    this.kairos.feedback(decisão.tarefa.id, resultado.sucesso ? 1 : 0);
  }

  private async executar(tarefa: any, contexto: any): Promise<{ sucesso: boolean; output: string }> {
    console.log(`[EVE] Executando: ${tarefa.descrição}`);
    return { sucesso: true, output: 'Executado' };
  }

  /**
   * Retorna estado atual
   */
  getEstado(): EstadoEve {
    return { ...this.estado };
  }

  /**
   * Acessa CACM
   */
  getCACM(): CACM {
    return this.cacm;
  }

  /**
   * Acessa autoDream
   */
  getAutoDream(): AutoDream {
    return this.autodream;
  }

  /**
   * Acessa KAIROS
   */
  getKAIROS(): KAIROS {
    return this.kairos;
  }
}

export default Eve;
