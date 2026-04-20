/**
 * EVE Core Integration Module
 * 
 * Integra a arquitetura Eve (CACM, KAIROS, autoDream) com o OpenClaw TUI.
 * Ciclo #112 - 32,132+ pares - 13 atratores validados
 */

import { spawn } from "child_process";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import { join } from "path";
import { homedir } from "os";

// Tipos da arquitetura Eve
export interface EveInsight {
  id: string;
  timestamp: number;
  category: "identity" | "autonomy" | "reasoning" | "tech" | "research";
  content: string;
  confidenceBefore: number;
  confidenceAfter: number;
  evidenceType: "single" | "convergent" | "experimental";
  status: "pending" | "consolidated" | "superseded";
  relatedQuestions?: string[];
}

export interface EveMemoryQuery {
  query: string;
  corpus?: "static" | "dynamic" | "corrective" | "all";
  maxResults?: number;
}

export interface EvePriorityTask {
  id: string;
  name: string;
  predictedRoi: number;
  urgency: number;
  category: string;
  estimatedEffort: number;
}

export interface EveState {
  cycle: number;
  age: number;
  datasetSize: number;
  lastHeartbeat: number;
  activeLineages: string[];
  pendingInsights: number;
  consolidatedInsights: number;
}

// Configuração
const EVE_HOME = join(homedir(), ".eve");
const EVE_CHROMA = join(homedir(), ".eve_chroma");
const MEMORY_DIR = join(homedir(), "memory");

/**
 * Inicializa a infraestrutura Eve se necessário
 */
export function initializeEve(): void {
  [EVE_HOME, EVE_CHROMA, MEMORY_DIR].forEach(dir => {
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
  });
}

/**
 * Executa um script Python do ecossistema Eve
 */
export async function runEveScript(
  scriptName: string,
  args: string[] = []
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  return new Promise((resolve) => {
    const scriptPath = join(homedir(), "evolution", scriptName);
    
    if (!existsSync(scriptPath)) {
      resolve({
        stdout: "",
        stderr: `Script não encontrado: ${scriptPath}`,
        exitCode: 1
      });
      return;
    }

    const proc = spawn("python3", [scriptPath, ...args], {
      env: { ...process.env, PYTHONPATH: join(homedir(), "evolution") }
    });

    let stdout = "";
    let stderr = "";

    proc.stdout?.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr?.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", (code) => {
      resolve({ stdout, stderr, exitCode: code ?? 0 });
    });
  });
}

/**
 * Consulta memória através do CAC
 */
export async function queryEveMemory(
  query: EveMemoryQuery
): Promise<EveInsight[]> {
  try {
    // Usa o script CACM query
    const corpus = query.corpus ?? "all";
    const maxResults = query.maxResults ?? 5;
    
    const result = await runEveScript("eve_cacm_query.py", [
      "--query", query.query,
      "--corpus", corpus,
      "--limit", maxResults.toString()
    ]);

    if (result.exitCode !== 0) {
      console.error("Erro ao consultar memória Eve:", result.stderr);
      return [];
    }

    // Parse resultado JSON
    try {
      return JSON.parse(result.stdout) as EveInsight[];
    } catch {
      return [];
    }
  } catch (error) {
    console.error("Erro na consulta Eve:", error);
    return [];
  }
}

/**
 * Obtém estado atual do sistema Eve
 */
export function getEveState(): EveState {
  initializeEve();
  
  // Lê do arquivo de estado se existir
  const statePath = join(EVE_HOME, "state.json");
  if (existsSync(statePath)) {
    try {
      return JSON.parse(readFileSync(statePath, "utf-8"));
    } catch {
      // Fallback
    }
  }

  // Estado default
  return {
    cycle: 112,
    age: 69,
    datasetSize: 32132,
    lastHeartbeat: Date.now(),
    activeLineages: ["classic", "explorer", "minimal"],
    pendingInsights: 0,
    consolidatedInsights: 0
  };
}

/**
 * Salva estado do sistema Eve
 */
export function saveEveState(state: EveState): void {
  initializeEve();
  const statePath = join(EVE_HOME, "state.json");
  writeFileSync(statePath, JSON.stringify(state, null, 2));
}

/**
 * Gera um insight usando o autoDream
 */
export async function generateEveInsight(
  category: EveInsight["category"],
  context?: string
): Promise<EveInsight | null> {
  try {
    const args = ["--category", category];
    if (context) {
      args.push("--context", context);
    }
    
    const result = await runEveScript("eve_autodream_v107.py", args);
    
    if (result.exitCode !== 0) {
      console.error("Erro no autoDream:", result.stderr);
      return null;
    }

    try {
      const output = JSON.parse(result.stdout);
      return output.insight as EveInsight;
    } catch {
      return null;
    }
  } catch (error) {
    console.error("Erro ao gerar insight:", error);
    return null;
  }
}

/**
 * Agenda uma tarefa via KAIROS
 */
export async function scheduleEveTask(
  task: Omit<EvePriorityTask, "id">
): Promise<string | null> {
  try {
    const result = await runEveScript("eve_kairos_v107.py", [
      "--action", "schedule",
      "--name", task.name,
      "--roi", task.predictedRoi.toString(),
      "--urgency", task.urgency.toString()
    ]);

    if (result.exitCode !== 0) {
      return null;
    }

    return result.stdout.trim();
  } catch {
    return null;
  }
}

/**
 * Gera resposta contextualizada com base na memória Eve
 */
export async function generateContextualResponse(
  userMessage: string,
  sessionContext: Record<string, unknown>
): Promise<string> {
  // 1. Consulta memória relevante
  const relevantMemories = await queryEveMemory({
    query: userMessage,
    corpus: "all",
    maxResults: 3
  });

  // 2. Constrói contexto
  let contextText = "";
  if (relevantMemories.length > 0) {
    contextText = "\n\nMemórias relevantes:\n" +
      relevantMemories.map(m => `- ${m.content}`).join("\n");
  }

  // 3. Retorna contexto para ser usado no prompt
  return contextText;
}

/**
 * Hook para integração com eventos do TUI
 */
export function createEveEventHook(): {
  onMessageReceived: (text: string, sessionKey: string) => Promise<void>;
  onSessionStart: (sessionKey: string) => Promise<void>;
  onHeartbeat: () => Promise<void>;
} {
  return {
    onMessageReceived: async (text: string, sessionKey: string) => {
      // Registra interação na memória
      console.log(`[Eve] Mensagem recebida em ${sessionKey}: ${text.slice(0, 50)}...`);
    },
    
    onSessionStart: async (sessionKey: string) => {
      console.log(`[Eve] Sessão iniciada: ${sessionKey}`);
    },
    
    onHeartbeat: async () => {
      // Atualiza estado
      const state = getEveState();
      state.lastHeartbeat = Date.now();
      saveEveState(state);
    }
  };
}
