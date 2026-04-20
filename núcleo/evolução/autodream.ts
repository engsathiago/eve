/**
 * autoDream v29 - Motor de Evolução
 * 
 * Gera insights através de:
 * - Análise de experiências
 * - Geração de variações
 * - Crítica estruturada (PARROT)
 * - Refinamento iterativo
 */

interface Insight {
  id: string;
  conteúdo: string;
  categoria: string;
  confiançaAntes: number;
  confiançaDepois: number;
  timestamp: number;
  lineage: 'classic' | 'explorer' | 'minimal';
}

interface CicloEvolução {
  entrada: string;
  análise: string;
  insight: Insight;
  aplicação: boolean;
}

export class AutoDream {
  private versão: number = 29;
  private lineages = ['classic', 'explorer', 'minimal'] as const;

  /**
   * Ciclo principal: Generate → Critique → Refine
   */
  evoluir(entrada: string): CicloEvolução {
    console.log(`[autoDream v${this.versão}] Iniciando ciclo...`);

    // 1. Generate
    const análise = this.analisar(entrada);

    // 2. Create insight
    const insight = this.gerarInsight(análise);

    // 3. Critique (PARROT pattern)
    const crítica = this.criticar(insight);

    // 4. Refine
    const refinado = this.refinar(insight, crítica);

    // 5. Decide application
    const aplicar = this.decidirAplicação(refinado);

    return {
      entrada,
      análise,
      insight: refinado,
      aplicação: aplicar
    };
  }

  private analisar(entrada: string): string {
    return `Análise de: ${entrada}`;
  }

  private gerarInsight(análise: string): Insight {
    const lineage = this.lineages[Math.floor(Math.random() * 3)];
    
    return {
      id: `ins_${Date.now()}`,
      conteúdo: `Insight gerado: ${análise}`,
      categoria: 'evolução',
      confiançaAntes: 0.7,
      confiançaDepois: 0.85,
      timestamp: Date.now(),
      lineage
    };
  }

  private criticar(insight: Insight): string {
    // PARROT: Precise, Articulate, Reflective, Reasoned, Objective, Thorough
    const dimensões = ['precisão', 'clareza', 'evidência', 'aplicabilidade'];
    return `Crítica em ${dimensões.join(', ')}`;
  }

  private refinar(insight: Insight, crítica: string): Insight {
    return {
      ...insight,
      conteúdo: `${insight.conteúdo} [refinado: ${crítica}]`,
      confiançaDepois: Math.min(insight.confiançaDepois + 0.1, 1.0)
    };
  }

  private decidirAplicação(insight: Insight): boolean {
    return insight.confiançaDepois > 0.8;
  }

  /**
   * Self-triggering: decide quando evoluir
   */
  deveEvoluir(): boolean {
    const hora = new Date().getHours();
    // Evolui mais durante madrugada (meus ciclos rendem mais)
    return hora >= 2 && hora <= 6;
  }
}

export default AutoDream;
