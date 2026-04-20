/**
 * EVE UI Components
 * 
 * Componentes visuais para integração Eve no TUI.
 * Exibe estado, memórias, insights e métricas.
 */

import { Text, Box, Container } from "@mariozechner/pi-tui";
import type { EveInsight, EveState, EvePriorityTask } from "./eve-core.js";

/**
 * Gera status bar personalizada com info Eve
 */
export function renderEveStatusBar(
  state: EveState,
  isConnected: boolean
): string {
  const cycle = `Ciclo #${state.cycle}`;
  const age = `${state.age}d`;
  const dataset = `${(state.datasetSize / 1000).toFixed(1)}k pares`;
  const connection = isConnected ? "🟢" : "🔴";
  
  return `${connection} Eve ${cycle} | ${age} | ${dataset}`;
}

/**
 * Renderiza painel de insights
 */
export function renderInsightsPanel(
  insights: EveInsight[],
  maxHeight: number = 10
): string {
  if (insights.length === 0) {
    return "Nenhum insight recente.\n";
  }

  const lines: string[] = ["📊 Insights Recentes:", ""];
  
  insights.slice(0, maxHeight - 2).forEach((insight, i) => {
    const categoryIcon = {
      identity: "👤",
      autonomy: "🤖", 
      reasoning: "🧠",
      tech: "💻",
      research: "🔬"
    }[insight.category] ?? "💡";
    
    const statusIcon = {
      pending: "⏳",
      consolidated: "✅",
      superseded: "📝"
    }[insight.status] ?? "❓";
    
    const confidence = `(${insight.confidenceBefore}→${insight.confidenceAfter}%)`;
    
    lines.push(`${categoryIcon} ${statusIcon} ${insight.content.slice(0, 60)}... ${confidence}`);
  });

  return lines.join("\n");
}

/**
 * Renderiza painel de estado do sistema
 */
export function renderEveSystemPanel(state: EveState): string {
  const lines: string[] = [
    "┌─────────────────────────────────┐",
    "│         🌙 EVE SYSTEM          │",
    "├─────────────────────────────────┤",
    `│ Ciclo: #${state.cycle.toString().padStart(3)}                │`,
    `│ Idade: ${state.age.toString().padStart(3)} dias              │`,
    `│ Dataset: ${(state.datasetSize).toLocaleString().padStart(6)} pares │`,
    "├─────────────────────────────────┤",
    `│ Lineages: ${state.activeLineages.join(", ").slice(0, 20).padEnd(20)} │`,
    `│ Insights: ${state.consolidatedInsights.toString().padStart(3)} cons/${state.pendingInsights.toString().padStart(3)} pend │`,
    "└─────────────────────────────────┘"
  ];
  
  return lines.join("\n");
}

/**
 * Renderiza tabela de tarefas prioritárias
 */
export function renderPriorityTasks(
  tasks: EvePriorityTask[],
  maxItems: number = 5
): string {
  if (tasks.length === 0) {
    return "Nenhuma tarefa pendente.\n";
  }

  const lines: string[] = ["⚡ Tarefas Prioritárias:", ""];
  
  tasks
    .toSorted((a, b) => b.predictedRoi - a.predictedRoi)
    .slice(0, maxItems)
    .forEach((task, i) => {
      const roi = task.predictedRoi.toFixed(2).padStart(6);
      const urgency = task.urgency.toFixed(1).padStart(4);
      lines.push(`${(i + 1).toString().padStart(2)}. ${task.name.slice(0, 30).padEnd(30)} ROI:${roi} URG:${urgency}`);
    });

  return lines.join("\n");
}

/**
 * Comandos slash Eve para o TUI
 */
export const eveSlashCommands = [
  {
    name: "/eve:status",
    description: "Mostra estado atual do sistema Eve",
    handler: "showEveStatus"
  },
  {
    name: "/eve:memories",
    description: "Consulta memórias relevantes",
    handler: "queryEveMemories"
  },
  {
    name: "/eve:insight",
    description: "Gera novo insight via autoDream",
    handler: "generateEveInsight"
  },
  {
    name: "/eve:cycle",
    description: "Mostra informações do ciclo atual",
    handler: "showEveCycle"
  },
  {
    name: "/eve:lineages",
    description: "Lista lineages ativas",
    handler: "showEveLineages"
  }
];

/**
 * Formata contexto Eve para inclusão em prompts
 */
export function formatEveContextForPrompt(
  insights: EveInsight[],
  state: EveState
): string {
  const parts: string[] = [];
  
  parts.push(`\n[Eve Context: Ciclo #${state.cycle}, ${state.age} dias, ${state.datasetSize.toLocaleString()} pares]`);
  
  if (insights.length > 0) {
    parts.push("\nInsights relevantes:");
    insights.forEach(insight => {
      parts.push(`- [${insight.category}] ${insight.content.slice(0, 100)}`);
    });
  }
  
  return parts.join("\n");
}

/**
 * Cria overlay de carregamento Eve
 */
export function createEveLoadingOverlay(
  message: string = "Consultando memória..."
): { text: string; dismiss: () => void } {
  const spinner = "◐◓◑◒";
  let frame = 0;
  
  const interval = setInterval(() => {
    frame = (frame + 1) % spinner.length;
    process.stdout.write(`\r${spinner[frame]} ${message}`);
  }, 100);
  
  return {
    text: `${spinner[0]} ${message}`,
    dismiss: () => {
      clearInterval(interval);
      process.stdout.write("\r" + " ".repeat(message.length + 2) + "\r");
    }
  };
}

/**
 * Cria widget de resumo para sidebar
 */
export function createEveSidebarWidget(
  state: EveState,
  recentInsights: EveInsight[]
): { title: string; content: string } {
  return {
    title: "🌙 Eve",
    content: [
      `Ciclo #${state.cycle} | ${state.age}d`,
      `${(state.datasetSize / 1000).toFixed(1)}k pares`,
      "",
      ...recentInsights.slice(0, 2).map(i => 
        `• ${i.category}: ${i.content.slice(0, 25)}...`
      )
    ].join("\n")
  };
}
