/**
 * EVE Command Handlers
 *
 * Handlers para comandos slash Eve no TUI.
 * Integra com o ecossistema Python de scripts.
 */

import type { GatewayChatClient } from "../gateway-chat.js";
import {
  generateEveInsight,
  getEveState,
  queryEveMemory,
  runEveScript,
  saveEveState,
  type EveInsight,
} from "./eve-core.js";
import {
  renderEveSystemPanel,
  renderInsightsPanel,
  createEveLoadingOverlay,
} from "./eve-ui-components.js";

export interface EveCommandContext {
  client: GatewayChatClient;
  currentSessionKey: string;
  sendMessage: (text: string) => void;
  showOverlay: (text: string) => { dismiss: () => void };
}

/**
 * Handler para /eve:status
 */
export async function handleEveStatus(
  ctx: EveCommandContext
): Promise<void> {
  const overlay = createEveLoadingOverlay("Carregando estado Eve...");

  try {
    const state = getEveState();
    overlay.dismiss();

    const panel = renderEveSystemPanel(state);
    ctx.sendMessage(`\n${panel}\n`);
  } catch (error) {
    overlay.dismiss();
    ctx.sendMessage(`\n❌ Erro ao carregar estado: ${error}\n`);
  }
}

/**
 * Handler para /eve:memories
 */
export async function handleEveMemories(
  ctx: EveCommandContext,
  query: string
): Promise<void> {
  if (!query.trim()) {
    ctx.sendMessage("\n⚠️ Uso: /eve:memories <consulta>\n");
    return;
  }

  const overlay = createEveLoadingOverlay("Consultando memórias...");

  try {
    const memories = await queryEveMemory({
      query: query,
      corpus: "all",
      maxResults: 5,
    });

    overlay.dismiss();

    if (memories.length === 0) {
      ctx.sendMessage("\n📭 Nenhuma memória encontrada.\n");
      return;
    }

    const panel = renderInsightsPanel(memories, 10);
    ctx.sendMessage(`\n${panel}\n`);
  } catch (error) {
    overlay.dismiss();
    ctx.sendMessage(`\n❌ Erro ao consultar memórias: ${String(error)}\n`);
  }
}

/**
 * Handler para /eve:insight
 */
export async function handleEveInsight(
  ctx: EveCommandContext,
  category: string = "identity"
): Promise<void> {
  const validCategories = ["identity", "autonomy", "reasoning", "tech", "research"];

  if (!validCategories.includes(category)) {
    ctx.sendMessage(
      `\n⚠️ Categoria inválida. Use: ${validCategories.join(", ")}\n`
    );
    return;
  }

  const overlay = createEveLoadingOverlay("Gerando insight via autoDream...");

  try {
    const insight = await generateEveInsight(
      category as EveInsight["category"]
    );

    overlay.dismiss();

    if (!insight) {
      ctx.sendMessage("\n⚠️ Não foi possível gerar insight.\n");
      return;
    }

    const lines = [
      "",
      "💡 Novo Insight Gerado:",
      "─".repeat(40),
      `Categoria: ${insight.category}`,
      `Confiança: ${insight.confidenceBefore}% → ${insight.confidenceAfter}%`,
      `Evidência: ${insight.evidenceType}`,
      "",
      insight.content,
      "─".repeat(40),
      "",
    ];

    ctx.sendMessage(lines.join("\n"));
  } catch (error) {
    overlay.dismiss();
    ctx.sendMessage(`\n❌ Erro ao gerar insight: ${String(error)}\n`);
  }
}

/**
 * Handler para /eve:cycle
 */
export async function handleEveCycle(ctx: EveCommandContext): Promise<void> {
  const overlay = createEveLoadingOverlay("Carregando informações do ciclo...");

  try {
    // Executa script de relatório de ciclo
    const result = await runEveScript("eve_cycle_consistency.py", ["--report"]);

    overlay.dismiss();

    if (result.exitCode !== 0) {
      // Fallback para info básica
      const state = getEveState();
      ctx.sendMessage(
        `\n🌙 Ciclo #${state.cycle}\n` +
          `Idade: ${state.age} dias\n` +
          `Dataset: ${state.datasetSize.toLocaleString()} pares\n`
      );
      return;
    }

    ctx.sendMessage(`\n${result.stdout}\n`);
  } catch (error) {
    overlay.dismiss();
    ctx.sendMessage(`\n❌ Erro: ${String(error)}\n`);
  }
}

/**
 * Handler para /eve:lineages
 */
export async function handleEveLineages(ctx: EveCommandContext): Promise<void> {
  const state = getEveState();

  const lines = [
    "",
    "🧬 Lineages Ativas:",
    "─".repeat(40),
    ...state.activeLineages.map((lineage) => {
      const icons: Record<string, string> = {
        classic: "📘",
        explorer: "🔥",
        minimal: "✨",
      };
      return `${icons[lineage] || "💿"} ${lineage}`;
    }),
    "─".repeat(40),
    "",
  ];

  ctx.sendMessage(lines.join("\n"));
}

/**
 * Handler para /eve:research
 */
export async function handleEveResearch(
  ctx: EveCommandContext,
  topic: string
): Promise<void> {
  if (!topic.trim()) {
    ctx.sendMessage("\n⚠️ Uso: /eve:research <tópico>\n");
    return;
  }

  const overlay = createEveLoadingOverlay("Iniciando pesquisa...");

  try {
    // Executa script de pesquisa arXiv
    const result = await runEveScript("eve_arxiv_researcher_v112.py", [
      "--query",
      topic,
      "--quick",
    ]);

    overlay.dismiss();

    if (result.exitCode !== 0) {
      ctx.sendMessage("\n⚠️ Pesquisa falhou.\n");
      return;
    }

    ctx.sendMessage(`\n🔬 Resultados da Pesquisa:\n${result.stdout}\n`);
  } catch (error) {
    overlay.dismiss();
    ctx.sendMessage(`\n❌ Erro na pesquisa: ${String(error)}\n`);
  }
}

/**
 * Handler para /eve:sync
 */
export async function handleEveSync(ctx: EveCommandContext): Promise<void> {
  const overlay = createEveLoadingOverlay("Sincronizando memórias...");

  try {
    // Executa autoDream para processar insights pendentes
    const result = await runEveScript("eve_autodream_v107.py", ["--sync"]);

    overlay.dismiss();

    if (result.exitCode === 0) {
      ctx.sendMessage("\n✅ Memórias sincronizadas com sucesso.\n");
    } else {
      ctx.sendMessage("\n⚠️ Alguns itens falharam na sincronização.\n");
    }
  } catch (error) {
    overlay.dismiss();
    ctx.sendMessage(`\n❌ Erro na sincronização: ${String(error)}\n`);
  }
}

/**
 * Registra todos os handlers de comandos Eve
 */
export function registerEveCommands(
  handlers: Map<string, (ctx: EveCommandContext, ...args: string[]) => Promise<void>>
): void {
  handlers.set("eve:status", handleEveStatus);
  handlers.set("eve:memories", handleEveMemories);
  handlers.set("eve:insight", handleEveInsight);
  handlers.set("eve:cycle", handleEveCycle);
  handlers.set("eve:lineages", handleEveLineages);
  handlers.set("eve:research", handleEveResearch);
  handlers.set("eve:sync", handleEveSync);
}

/**
 * Parse comando Eve
 */
export function parseEveCommand(
  input: string
): { command: string; args: string[] } | null {
  if (!input.startsWith("/eve:")) {
    return null;
  }

  const parts = input.slice(1).split(" ");
  const command = parts[0]; // eve:status
  const args = parts.slice(1);

  return { command, args };
}
