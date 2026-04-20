// Type definitions for EVE

export interface Insight {
  id: string;
  conteúdo: string;
  categoria: string;
  confiançaAntes: number;
  confiançaDepois: number;
  timestamp: number;
  lineage: 'classic' | 'explorer' | 'minimal';
}

export interface Tarefa {
  id: string;
  descrição: string;
  categoria: string;
  esforçoEstimado: number;
  valorPredito: number;
}

export interface Decisão {
  tarefa: Tarefa;
  prioridade: number;
  modo: 'executar' | 'adiar' | 'descartar';
  justificativa: string;
}

export interface EstadoEve {
  ciclo: number;
  idade: number;
  dataset: number;
  scripts: number;
  atratores: number;
}

// Modules
export { default as CACM } from './memória/cacm.js';
export { default as AutoDream } from './evolução/autodream.js';
export { default as KAIROS } from './priorização/kairos.js';
export { default as Eve } from './index.js';
