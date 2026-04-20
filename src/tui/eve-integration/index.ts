/**
 * EVE Integration Module - Export
 * 
 * Ponto de entrada para integração Eve com OpenClaw TUI.
 */

// Core
export {
  initializeEve,
  runEveScript,
  queryEveMemory,
  getEveState,
  saveEveState,
  generateEveInsight,
  scheduleEveTask,
  generateContextualResponse,
  createEveEventHook,
  type EveInsight,
  type EveMemoryQuery,
  type EvePriorityTask,
  type EveState,
} from "./eve-core.js";

// UI Components
export {
  renderEveStatusBar,
  renderInsightsPanel,
  renderEveSystemPanel,
  renderPriorityTasks,
  eveSlashCommands,
  formatEveContextForPrompt,
  createEveLoadingOverlay,
  createEveSidebarWidget,
} from "./eve-ui-components.js";

// Command Handlers
export {
  handleEveStatus,
  handleEveMemories,
  handleEveInsight,
  handleEveCycle,
  handleEveLineages,
  handleEveResearch,
  handleEveSync,
  registerEveCommands,
  parseEveCommand,
  type EveCommandContext,
} from "./eve-command-handlers.js";

// TUI Adapter
export {
  initializeEveInTui,
  getEveSlashCommands,
  enrichMessageWithEveContext,
  handleEveTuiCommand,
  getEveStatusBarText,
  createEveTuiHooks,
  getEvePromptMetadata,
  eveState,
} from "./eve-tui-adapter.js";
