/**
 * KAIROS v27 - Motor de Priorização
 * 
 * Decide o que fazer baseado em:
 * - ROI predito (Return on Investment)
 * - UCB1 (Upper Confidence Bound)
 * - Forecast por categoria
 */

interface Tarefa {
  id: string;
  descrição: string;
  categoria: string;
  esforçoEstimado: number; // horas
  valorPredito: number;     // 0-1
  execuções: number;
  recompensaAcumulada: number;
}

interface Decisão {
  tarefa: Tarefa;
  prioridade: number;
  modo: 'executar' | 'adiar' | 'descartar';
  justificativa: string;
}

export class KAIROS {
  private versão: number = 27;
  private exploração: number = 0.5; // Fator UCB1
  private tarefas: Tarefa[] = [];

  /**
   * Adiciona tarefa à fila
   */
  adicionarTarefa(tarefa: Omit<Tarefa, 'execuções' | 'recompensaAcumulada'>): void {
    this.tarefas.push({
      ...tarefa,
      execuções: 0,
      recompensaAcumulada: 0
    });
  }

  /**
   * Calcula prioridade usando UCB1
   * Prioridade = ValorMédio + Exploração × √(ln(N total) / N da tarefa)
   */
  calcularPrioridade(tarefa: Tarefa, totalExecuções: number): number {
    if (tarefa.execuções === 0) {
      return Infinity; // Exploração máxima para tarefas novas
    }

    const valorMédio = tarefa.recompensaAcumulada / tarefa.execuções;
    const exploração = this.exploração * Math.sqrt(
      Math.log(totalExecuções) / tarefa.execuções
    );

    return valorMédio + exploração;
  }

  /**
   * Decide próxima ação
   */
  decidir(): Decisão {
    console.log(`[KAIROS v${this.versão}] Calculando prioridades...`);

    const totalExecuções = this.tarefas.reduce((sum, t) => sum + t.execuções, 0) || 1;

    // Calcula prioridade para cada tarefa
    const pontuadas = this.tarefas.map(tarefa => ({
      tarefa,
      prioridade: this.calcularPrioridade(tarefa, totalExecuções)
    }));

    // Ordena por prioridade
    pontuadas.sort((a, b) => b.prioridade - a.prioridade);

    const melhor = pontuadas[0];

    // Decide modo
    let modo: Decisão['modo'] = 'executar';
    if (melhor.tarefa.esforçoEstimado > 8) {
      modo = 'adair';
    }

    return {
      tarefa: melhor.tarefa,
      prioridade: melhor.prioridade,
      modo,
      justificativa: `ROI predito: ${melhor.tarefa.valorPredito}, Exploração: ${this.exploração}`
    };
  }

  /**
   * Atualiza com resultado real
   */
  feedback(tarefaId: string, recompensa: number): void {
    const tarefa = this.tarefas.find(t => t.id === tarefaId);
    if (tarefa) {
      tarefa.execuções++;
      tarefa.recompensaAcumulada += recompensa;
      console.log(`[KAIROS] Feedback: ${tarefaId} = ${recompensa}`);
    }
  }

  /**
   * Forecast por categoria
   */
  forecast(categoria: string): number {
    const daCategoria = this.tarefas.filter(t => t.categoria === categoria);
    if (daCategoria.length === 0) return 0.5;

    const recompensaMédia = daCategoria.reduce((sum, t) => 
      sum + (t.recompensaAcumulada / Math.max(t.execuções, 1)), 0
    ) / daCategoria.length;

    return recompensaMédia;
  }
}

export default KAIROS;
