import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { ProjectMemoryStore } from "./db.js";
import { ProjectMemoryService, UserMemoryService } from "./memoryService.js";
import { currentProjectRoot, defaultDatabasePath } from "./paths.js";
import { confidenceValues, memoryKinds, userMemoryKinds } from "./types.js";

const memoryKindSchema = z
  .enum(memoryKinds)
  .describe(
    "Memory kind: decision, convention, architecture, workflow, preference, gotcha, bug, dependency, testing, or handoff."
  );
const userMemoryKindSchema = z
  .enum(userMemoryKinds)
  .describe(
    "User memory kind: preference, behavior, context, workflow, convention, tool_preference, or communication."
  );
const confidenceSchema = z
  .enum(confidenceValues)
  .describe("Confidence level: high (confirmed), medium (inferred, default), or low (uncertain).");

const projectRootField = z
  .string()
  .describe("Absolute path to the project root. Used to scope memory to the correct project.");
const idField = z.number().int().positive().describe("Numeric id of the memory record.");
const contentField = z
  .string()
  .describe(
    "The durable memory content. Must be specific, at least 40 characters or 7 words, non-vague, and secret-free."
  );
const summaryField = z.string().optional().describe("Optional short title shown in listings.");
const whyUsefulLaterField = z
  .string()
  .describe(
    "Required: explain specifically why a future agent needs this memory. If you cannot justify it, do not store it."
  );
const tagsField = z
  .array(z.string())
  .optional()
  .describe("Lowercase alphanumeric tags (hyphens and underscores allowed) for filtering.");
const reasonField = z.string().optional().describe("Human-readable reason for this change, stored in the audit log.");
const includeArchivedField = z.boolean().optional().describe("Include soft-deleted memories in results.");
const hardDeleteField = z
  .boolean()
  .optional()
  .describe(
    "Set true to permanently delete the record. An audit event is always kept. Default is soft-delete (archive)."
  );

export function createProjectMemoryServer(service: ProjectMemoryService, userService: UserMemoryService): McpServer {
  const server = new McpServer({
    name: "myagents-project-memory",
    version: "0.1.0"
  });

  // ── Project memory tools ──────────────────────────────────────────────────

  server.registerTool(
    "memory.remember",
    {
      title: "Remember project knowledge",
      description:
        "Store a durable, reusable fact scoped to this project. Call this after completing work when you learned something non-obvious: a decision with rationale, a convention, an architecture fact, a gotcha, or a recurring bug cause. Rejected if content is too short, vague, a duplicate, or contains secrets.",
      inputSchema: {
        projectRoot: projectRootField,
        kind: memoryKindSchema,
        content: contentField,
        summary: summaryField,
        whyUsefulLater: whyUsefulLaterField,
        tags: tagsField,
        confidence: confidenceSchema.optional(),
        source: z.string().optional().describe("Where this knowledge came from, e.g. 'agent' or 'user'."),
        sourceRef: z.string().optional().describe("Optional reference such as a file path, PR number, or test command.")
      }
    },
    async (input) => jsonResult(service.remember(input))
  );

  server.registerTool(
    "memory.search",
    {
      title: "Search project memory",
      description:
        "Full-text search across project memory using BM25 ranking with a LIKE fallback. Call this at task start with specific terms — file names, function names, domain concepts, error messages. Do not use generic questions as queries. Returns up to k results ordered by relevance, confidence, and recency.",
      inputSchema: {
        projectRoot: projectRootField,
        query: z.string().describe("Specific search terms: file names, function names, concepts, or error messages."),
        k: z.number().int().positive().max(25).optional().describe("Maximum results to return. Default 8, max 25."),
        kinds: z.array(memoryKindSchema).optional().describe("Restrict results to these memory kinds."),
        tags: tagsField,
        includeArchived: includeArchivedField
      }
    },
    async (input) => jsonResult(service.search(input))
  );

  server.registerTool(
    "memory.get",
    {
      title: "Get project memory by id",
      description:
        "Fetch a single project memory record by its numeric id. Use when you already have an id from search results or the brief and need the full record details.",
      inputSchema: {
        projectRoot: projectRootField,
        id: idField
      }
    },
    async ({ projectRoot, id }) => jsonResult(service.get(projectRoot, id))
  );

  server.registerTool(
    "memory.project_brief",
    {
      title: "Project memory brief",
      description:
        "Return a compact summary of the most important project memory grouped into: conventions (style/preference), decisions (architecture), pitfalls (gotchas/bugs), and 8 most recently updated entries. Read this at the start of every non-trivial task before calling memory.search for specifics.",
      inputSchema: {
        projectRoot: projectRootField
      }
    },
    async ({ projectRoot }) => jsonResult(service.projectBrief(projectRoot))
  );

  server.registerTool(
    "memory.update",
    {
      title: "Update project memory",
      description:
        "Correct, refine, or soft-delete a project memory record. Use when a stored memory is inaccurate, incomplete, or outdated — the repo always wins over memory. Prefer updating over forgetting when the core fact is still valid but needs correction. Secret-containing updates are rejected.",
      inputSchema: {
        projectRoot: projectRootField,
        id: idField,
        content: contentField.optional(),
        summary: summaryField,
        whyUsefulLater: whyUsefulLaterField.optional(),
        tags: tagsField,
        confidence: confidenceSchema.optional(),
        archive: z.boolean().optional().describe("Set true to soft-delete this memory."),
        reason: reasonField
      }
    },
    async (input) => jsonResult(service.update(input))
  );

  server.registerTool(
    "memory.forget",
    {
      title: "Forget project memory",
      description:
        "Soft-delete a project memory so it no longer appears in search results. Default is archive (reversible); set hardDelete: true only when the user explicitly requests permanent removal. A project-scoped audit event is always kept.",
      inputSchema: {
        projectRoot: projectRootField,
        id: idField,
        hardDelete: hardDeleteField,
        reason: reasonField
      }
    },
    async (input) => jsonResult(service.forget(input))
  );

  server.registerTool(
    "memory.capture_task_summary",
    {
      title: "Capture durable task learnings",
      description:
        "Store a batch of end-of-task learnings as handoff memories. Each entry in durableLearnings is independently quality-checked — failures are counted in skipped rather than aborting the whole batch. Set shouldRemember: false to skip storage without error (useful when nothing durable was learned).",
      inputSchema: {
        projectRoot: projectRootField,
        taskSummary: z.string().describe("Short description of the completed task."),
        durableLearnings: z
          .array(z.string())
          .describe("Durable facts learned during the task. Each is independently quality-checked."),
        testsRun: z
          .array(z.string())
          .default([])
          .describe("Test commands or suites that were run, recorded in the source reference."),
        shouldRemember: z.boolean().describe("Set false to skip storage entirely when nothing durable was learned.")
      }
    },
    async (input) => jsonResult(service.captureTaskSummary(input))
  );

  server.registerTool(
    "memory.export_project",
    {
      title: "Export project memory",
      description:
        "Export all project memory records and audit events as JSON for backup or migration to another checkout. Pass the result to memory.import_project on the target project.",
      inputSchema: {
        projectRoot: projectRootField,
        includeArchived: includeArchivedField
      }
    },
    async ({ projectRoot, includeArchived }) => jsonResult(service.exportProject(projectRoot, includeArchived ?? false))
  );

  server.registerTool(
    "memory.import_project",
    {
      title: "Import project memory",
      description:
        "Import a JSON export produced by memory.export_project into a project. Validates all memory kinds and required fields. Duplicates and quality failures are silently skipped and counted in the result.",
      inputSchema: {
        projectRoot: projectRootField,
        exportJson: z.unknown().describe("JSON object produced by memory.export_project.")
      }
    },
    async ({ projectRoot, exportJson }) => jsonResult(service.importProject(projectRoot, exportJson))
  );

  server.registerTool(
    "memory.link_project_paths",
    {
      title: "Link project checkout paths",
      description:
        "Link an additional filesystem path to the same project memory as the primary root. Use this when the same repository is checked out at multiple locations and you want both paths to share memory. Rejected if the git remotes do not match.",
      inputSchema: {
        primaryProjectRoot: z.string().describe("The project root whose memory is the canonical store."),
        additionalProjectRoot: z.string().describe("Another checkout path to link to the primary project's memory.")
      }
    },
    async ({ primaryProjectRoot, additionalProjectRoot }) =>
      jsonResult(service.linkProjectPaths(primaryProjectRoot, additionalProjectRoot))
  );

  server.registerTool(
    "memory.possible_project_matches",
    {
      title: "Find possible project memory matches",
      description:
        "Find other known project paths that share the same git remote fingerprint as the given root. Use this to discover related checkouts before deciding whether to link them with memory.link_project_paths. Does not link paths automatically.",
      inputSchema: {
        projectRoot: projectRootField
      }
    },
    async ({ projectRoot }) => jsonResult(service.possibleProjectMatches(projectRoot))
  );

  // ── User memory tools ─────────────────────────────────────────────────────

  server.registerTool(
    "user.remember",
    {
      title: "Remember user knowledge",
      description:
        "Store a durable, cross-project fact about the user — their preferences, recurring behaviors, background context, global conventions, tool choices, or communication style. Applied across all projects and sessions. Rejected if content is too short, vague, a duplicate, or contains secrets.",
      inputSchema: {
        kind: userMemoryKindSchema,
        content: contentField,
        summary: summaryField,
        whyUsefulLater: whyUsefulLaterField,
        tags: tagsField,
        confidence: confidenceSchema.optional(),
        source: z.string().optional().describe("Where this was observed, e.g. 'agent' or 'user'."),
        sourceRef: z.string().optional().describe("Optional contextual reference.")
      }
    },
    async (input) => jsonResult(userService.remember(input))
  );

  server.registerTool(
    "user.search",
    {
      title: "Search user memory",
      description:
        "Full-text search across global user memory. Use at session start alongside user.brief to load context relevant to the current task domain. Returns up to k results ordered by relevance, confidence, and recency.",
      inputSchema: {
        query: z
          .string()
          .describe("Search terms relevant to the current task or domain, e.g. 'typescript', 'git workflow'."),
        k: z.number().int().positive().max(25).optional().describe("Maximum results to return. Default 8, max 25."),
        kinds: z.array(userMemoryKindSchema).optional().describe("Restrict results to these user memory kinds."),
        tags: tagsField,
        includeArchived: includeArchivedField
      }
    },
    async (input) => jsonResult(userService.search(input))
  );

  server.registerTool(
    "user.get",
    {
      title: "Get user memory by id",
      description:
        "Fetch a single user memory record by its numeric id. Use when you already have an id from search results or the brief and need the full record details.",
      inputSchema: {
        id: idField
      }
    },
    async ({ id }) => jsonResult(userService.get(id))
  );

  server.registerTool(
    "user.brief",
    {
      title: "User memory brief",
      description:
        "Return a compact summary of all active user memory grouped into: preferences (preference/convention/tool_preference), behaviors (behavior/workflow/communication), context, and 8 most recently updated entries. Read this at the start of every session before doing any work — it is the primary way to understand the user.",
      inputSchema: {}
    },
    async () => jsonResult(userService.brief())
  );

  server.registerTool(
    "user.update",
    {
      title: "Update user memory",
      description:
        "Correct, refine, or soft-delete a user memory record. Use when observed behavior contradicts a stored memory — update rather than ignore stale entries. Secret-containing updates are rejected.",
      inputSchema: {
        id: idField,
        content: contentField.optional(),
        summary: summaryField,
        whyUsefulLater: whyUsefulLaterField.optional(),
        tags: tagsField,
        confidence: confidenceSchema.optional(),
        archive: z.boolean().optional().describe("Set true to soft-delete this memory."),
        reason: reasonField
      }
    },
    async (input) => jsonResult(userService.update(input))
  );

  server.registerTool(
    "user.forget",
    {
      title: "Forget user memory",
      description:
        "Soft-delete a user memory so it no longer appears in search results. Default is archive (reversible); set hardDelete: true only when the user explicitly requests permanent removal.",
      inputSchema: {
        id: idField,
        hardDelete: hardDeleteField,
        reason: reasonField
      }
    },
    async (input) => jsonResult(userService.forget(input))
  );

  server.registerTool(
    "user.export",
    {
      title: "Export user memory",
      description:
        "Export all user memory records and audit events as JSON for backup or migration. Pass the result to user.import on another instance.",
      inputSchema: {
        includeArchived: includeArchivedField
      }
    },
    async ({ includeArchived }) => jsonResult(userService.export(includeArchived ?? false))
  );

  server.registerTool(
    "user.import",
    {
      title: "Import user memory",
      description:
        "Import a JSON export produced by user.export. Validates all memory kinds and required fields. Duplicates and quality failures are silently skipped and counted in the result.",
      inputSchema: {
        exportJson: z.unknown().describe("JSON object produced by user.export.")
      }
    },
    async ({ exportJson }) => jsonResult(userService.import(exportJson))
  );

  // ── User memory resources ─────────────────────────────────────────────────

  registerResource(
    server,
    "user-memory-brief",
    "memory://user/brief",
    "User Memory: Full Brief",
    "All active user memory grouped into preferences, behaviors, context, and 8 most recent entries. Read this at session start to understand the user before doing any work.",
    () => userService.brief()
  );
  registerResource(
    server,
    "user-memory-preferences",
    "memory://user/preferences",
    "User Memory: Preferences",
    "Active user memories of kind preference, convention, and tool_preference — coding style, language choices, formatting rules, and tool setups. Up to 8 entries ranked by confidence and usage.",
    () => userService.brief().preferences
  );
  registerResource(
    server,
    "user-memory-behaviors",
    "memory://user/behaviors",
    "User Memory: Behaviors",
    "Active user memories of kind behavior, workflow, and communication — recurring habits, work process patterns, and how the user prefers to receive information. Up to 8 entries ranked by confidence and usage.",
    () => userService.brief().behaviors
  );
  registerResource(
    server,
    "user-memory-context",
    "memory://user/context",
    "User Memory: Context",
    "Active user memories of kind context — role, team, domain, experience level, and background. Up to 8 entries ranked by confidence and usage.",
    () => userService.brief().context
  );

  // ── User memory prompts ───────────────────────────────────────────────────

  server.registerPrompt(
    "user_memory_bootstrap",
    {
      title: "Bootstrap user memory",
      description:
        "Instructs the agent to read user memory before starting work so it can apply the user's preferences, behaviors, and context throughout the session.",
      argsSchema: {}
    },
    () => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: [
              "Before starting work, read memory://user/brief to understand the user's preferences, behaviors, and context.",
              "Apply this knowledge throughout the session: respect stated preferences, adapt to known workflows, and avoid patterns the user dislikes.",
              "User memory is a guide, not a constraint — current instructions always take precedence."
            ].join("\n")
          }
        }
      ]
    })
  );

  server.registerPrompt(
    "user_memory_update",
    {
      title: "Update user memory",
      description:
        "Instructs the agent to review the session for durable cross-project facts about the user and store them with user.remember.",
      argsSchema: {
        sessionSummary: z.string().optional().describe("Brief description of what happened in this session.")
      }
    },
    ({ sessionSummary }) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: [
              "Decide whether this session revealed durable knowledge about the user worth storing globally.",
              "Store only stable facts: consistent preferences, recurring behaviors, background context, tool choices, or communication style.",
              "Do not store: secrets, one-off task details, temporary opinions, or facts specific to a single project.",
              sessionSummary ? `Session summary: ${sessionSummary}` : undefined
            ]
              .filter(Boolean)
              .join("\n")
          }
        }
      ]
    })
  );

  // ── Project memory resources ──────────────────────────────────────────────

  registerResource(
    server,
    "project-memory-brief",
    "memory://project/current/brief",
    "Project Memory: Full Brief",
    "All active project memory for the current project grouped into conventions, decisions, pitfalls, and 8 most recently updated entries. Read this at task start before searching for specifics.",
    () => service.projectBrief(currentProjectRoot())
  );
  registerResource(
    server,
    "project-memory-conventions",
    "memory://project/current/conventions",
    "Project Memory: Conventions",
    "Active convention and preference memories for the current project — coding style, naming rules, and project-specific preferences. Up to 8 entries ranked by confidence and usage.",
    () => service.projectBrief(currentProjectRoot()).conventions
  );
  registerResource(
    server,
    "project-memory-decisions",
    "memory://project/current/decisions",
    "Project Memory: Decisions",
    "Active decision and architecture memories for the current project — design choices with rationale, module boundaries, and key relationships. Up to 8 entries ranked by confidence and usage.",
    () => service.projectBrief(currentProjectRoot()).decisions
  );
  registerResource(
    server,
    "project-memory-pitfalls",
    "memory://project/current/pitfalls",
    "Project Memory: Pitfalls",
    "Active gotcha and bug memories for the current project — surprising behavior, common traps, and recurring bug root causes. Up to 8 entries ranked by confidence and usage.",
    () => service.projectBrief(currentProjectRoot()).pitfalls
  );
  registerResource(
    server,
    "project-memory-recent",
    "memory://project/current/recent",
    "Project Memory: Recent",
    "The 8 most recently updated active memories for the current project across all kinds. Useful for picking up where a previous agent left off.",
    () => service.projectBrief(currentProjectRoot()).recent
  );

  // ── Project memory prompts ────────────────────────────────────────────────

  server.registerPrompt(
    "memory_bootstrap",
    {
      title: "Bootstrap project memory",
      description:
        "Instructs the agent to read project memory before starting a task so it has relevant conventions, decisions, and pitfalls loaded before making any changes.",
      argsSchema: {
        task: z.string().optional().describe("Brief description of the upcoming task for targeted search.")
      }
    },
    ({ task }) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: [
              "Before planning this task, read memory://project/current/brief and search project memory for task-specific terms.",
              "Treat memory as indexed notes, not authority. Current user instructions, repo files, tests, and official docs override memory.",
              task ? `Task: ${task}` : undefined
            ]
              .filter(Boolean)
              .join("\n")
          }
        }
      ]
    })
  );

  server.registerPrompt(
    "memory_handoff",
    {
      title: "Capture task memory",
      description:
        "Instructs the agent to review what was learned during a task and store only durable, reusable project knowledge — not task status or command output.",
      argsSchema: {
        taskSummary: z.string().describe("Description of the completed task."),
        testsRun: z.string().optional().describe("Tests or test suites that were run.")
      }
    },
    ({ taskSummary, testsRun }) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: [
              "Decide whether this task produced durable project knowledge worth storing.",
              "Store only reusable decisions, conventions, gotchas, preferences, architecture facts, or recurring bug causes.",
              "Do not store secrets, command output, one-off task status, or facts obvious from current files without added interpretation.",
              `Task summary: ${taskSummary}`,
              testsRun ? `Tests run: ${testsRun}` : undefined
            ]
              .filter(Boolean)
              .join("\n")
          }
        }
      ]
    })
  );

  server.registerPrompt(
    "memory_cleanup",
    {
      title: "Clean stale project memory",
      description:
        "Instructs the agent to audit project memory for stale, contradictory, or low-confidence entries and update or archive them after verifying against current repo files.",
      argsSchema: {
        topic: z.string().optional().describe("Narrow the cleanup to memories related to a specific topic or file.")
      }
    },
    ({ topic }) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: [
              "Search project memory for stale, contradictory, low-confidence, or no-longer-useful entries.",
              "Verify against current repo files before updating or archiving memory.",
              topic ? `Topic: ${topic}` : undefined
            ]
              .filter(Boolean)
              .join("\n")
          }
        }
      ]
    })
  );

  return server;
}

export async function runServer(): Promise<void> {
  const store = new ProjectMemoryStore(defaultDatabasePath());
  const service = new ProjectMemoryService(store);
  const userService = new UserMemoryService(store);
  const server = createProjectMemoryServer(service, userService);
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

function registerResource(
  server: McpServer,
  name: string,
  uri: string,
  title: string,
  description: string,
  read: () => unknown
): void {
  server.registerResource(name, uri, { title, description, mimeType: "application/json" }, async (resourceUri) => ({
    contents: [
      {
        uri: resourceUri.href,
        mimeType: "application/json",
        text: JSON.stringify(read(), null, 2)
      }
    ]
  }));
}

function jsonResult(value: unknown): { content: Array<{ type: "text"; text: string }> } {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(value, null, 2)
      }
    ]
  };
}
