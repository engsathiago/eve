/**
 * EVE TUI Adapter
 * 
 * Adaptador que conecta a arquitetura Eve ao TUI do OpenClaw
 * sem modificar os arquivos originais.
 */

import type { SlashCommand } from "@mariozechner/pi-tui";
import type { OpenClawConfig } from "../../config/types.js";
import type { GatewayChatClient } from "../gateway-chat.js";
import type { ChatLog } from "../components/chat-log.js";
import {
  getEveState,
  queryEveMemory,
  generateEveInsight,
  initializeEve,
  type EveState,
  type EveInsight,
} from "./eve-core.js";
import { renderEveSystemPanel } from "./eve-ui-components.js";
import {
  handleEveStatus,
  handleEveMemories,
  handleEveInsight,
  handleEveCycle,
  handleEveLineages,
  parseEveCommand,
  type EveCommandContext,
} from "./eve-command-handlers.js";

// Estado Eve no TUI
let eveState: EveState | null = null;
let eveInitialized = false;

/**
 * Inicializa a integração Eve no TUI
 */
export function initializeEveInTui(): void {
  if (eveInitialized) {return;}
  
  initializeEve();
  eveState = getEveState();
  eveInitialized = true;
  
  console.log(`[Eve] Integração inicializada - Ciclo #${eveState.cycle}`);
}

/**
 * Obtém comandos slash Eve
 */
export function getEveSlashCommands(): SlashCommand[] {
  return [
    { name: "eve", description: "Mostra status do sistema Eve" },
    { name: "eve:status", description: "Estado completo do sistema" },
    { name: "eve:memories", description: "Consulta memórias: /eve:memories <query>" },
    { name: "eve:insight", description: "Gera insight: /eve:insight [categoria]" },
    { name: "eve:cycle", description: "Informações do ciclo atual" },
    { name: "eve:lineages", description: "Lista lineages ativas" },
  ];
}

/**
 * Hook de mensagem para enriquecer com contexto Eve
 */
export async function enrichMessageWithEveContext(
  message: string
): Promise<{ enrichedMessage: string; eveContext?: string }> {
  if (!eveInitialized) {
    initializeEveInTui();
  }

  // Verifica se é comando Eve
  const eveCmd = parseEveCommand(message);
  if (eveCmd) {
    return { enrichedMessage: message };
  }

  // Para mensagens normais, consulta memória relevante
  try {
    const memories = await queryEveMemory({
      query: message,
      corpus: "dynamic",
      maxResults: 3,
    });

    if (memories.length === 0) {
      return { enrichedMessage: message };
    }

    const eveContext = memories
      .map((m) => `[${m.category}] ${m.content.slice(0, 100)}`)
      .join("\n");

    return {
      enrichedMessage: message,
      eveContext: `\n[Eve Context]\n${eveContext}\n`,
    };
  } catch {
    return { enrichedMessage: message };
  }
}

/**
 * Handler para comandos Eve
 */
export async function handleEveTuiCommand(
  command: string,
  args: string,
  ctx: {
    client: GatewayChatClient;
    chatLog: ChatLog;
    currentSessionKey: string;
    addSystemMessage: (text: string) => void;
  }
): Promise<boolean> {
  if (!command.startsWith("eve")) {
    return false;
  }

  if (!eveInitialized) {
    initializeEveInTui();
  }

  const fullCommand = args ? `/${command} ${args}` : `/${command}`;
  const parsed = parseEveCommand(fullCommand);
  
  if (!parsed) {
    return false;
  }

  // Cria contexto de comando
  const cmdCtx: EveCommandContext = {
    client: ctx.client,
    currentSessionKey: ctx.currentSessionKey,
    sendMessage: (text: string) => {
      ctx.addSystemMessage(text);
    },
    showOverlay: (text: string) => ({
      dismiss: () => {
        // No-op no TUI
      },
    }),
  };

  try {
    switch (parsed.command) {
      case "eve:status":
      case "eve":
        await handleEveStatus(cmdCtx);
        break;
      case "eve:memories":
        await handleEveMemories(cmdCtx, parsed.args.join(" "));
        break;
      case "eve:insight":
        await handleEveInsight(cmdCtx, parsed.args[0]);
        break;
      case "eve:cycle":
        await handleEveCycle(cmdCtx);
        break;
      case "eve:lineages":
        await handleEveLineages(cmdCtx);
        break;
      default:
        ctx.addSystemMessage(`\n⚠️ Comando Eve desconhecido: ${parsed.command}\n`);
        return true;
    }
  } catch (error) {
    ctx.addSystemMessage(`\n❌ Erro no comando Eve: ${error}\n`);
  }

  return true;
}

/**
 * Atualiza o header do TUI com info Eve
 */
export function getEveStatusBarText(
  baseStatus: string,
  isConnected: boolean
): string {
  if (!eveState) {
    eveState = getEveState();
  }

  const connectionIcon = isConnected ? "🟢" : "🔴";
  return `${connectionIcon} Eve #${eveState.cycle} | ${baseStatus}`;
}

/**
 * Hook para eventos do TUI
 */
export function createEveTuiHooks() {
  return {
    onSessionStart: (sessionKey: string) => {
      console.log(`[Eve] Sessão iniciada: ${sessionKey}`);
    },
    
    onMessageSent: (text: string) => {
      // Registra interação
      if (!text.startsWith("/")) {
        console.log(`[Eve] Mensagem: ${text.slice(0, 50)}...`);
      }
    },
    
    onHeartbeat: () => {
      if (eveState) {
        eveState.lastHeartbeat = Date.now();
      }
    },
  };
}

/**
 * Retorna metadados para injeção em prompts
 */
export function getEvePromptMetadata(): Record<string, string> {
  if (!eveState) {
    eveState = getEveState();
  }

  return {
    eveCycle: eveState.cycle.toString(),
    eveAge: `${eveState.age}d`,
    eveDataset: eveState.datasetSize.toLocaleString(),
    eveLineages: eveState.activeLineages.join(","),
  };
}

export { eveState };
