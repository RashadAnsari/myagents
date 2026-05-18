import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { ProjectMemoryStore } from "./db.js";
import { ProjectMemoryService, UserMemoryService } from "./memoryService.js";
import { currentProjectRoot, defaultDatabasePath } from "./paths.js";
import { confidenceValues, memoryKinds, userMemoryKinds } from "./types.js";

const memoryKindSchema = z.enum(memoryKinds);
const userMemoryKindSchema = z.enum(userMemoryKinds);
const confidenceSchema = z.enum(confidenceValues);

export function createProjectMemoryServer(
  service: ProjectMemoryService,
  userService: UserMemoryService
): McpServer {
  const server = new McpServer({
    name: "myagents-project-memory",
    version: "0.1.0"
  });

  server.registerTool(
    "memory.remember",
    {
      title: "Remember project knowledge",
      description: "Store durable, reusable project knowledge after quality and secret checks.",
      inputSchema: {
        projectRoot: z.string().describe("Absolute or relative project root path."),
        kind: memoryKindSchema,
        content: z.string().describe("Specific durable memory content."),
        summary: z.string().optional(),
        whyUsefulLater: z.string().describe("Required by policy: why future agents will need this."),
        tags: z.array(z.string()).optional(),
        confidence: confidenceSchema.optional(),
        source: z.string().optional(),
        sourceRef: z.string().optional()
      }
    },
    async (input) => jsonResult(service.remember(input))
  );

  server.registerTool(
    "memory.search",
    {
      title: "Search project memory",
      description: "Search durable project memory with optional kind and tag filters.",
      inputSchema: {
        projectRoot: z.string(),
        query: z.string(),
        k: z.number().int().positive().max(25).optional(),
        kinds: z.array(memoryKindSchema).optional(),
        tags: z.array(z.string()).optional(),
        includeArchived: z.boolean().optional()
      }
    },
    async (input) => jsonResult(service.search(input))
  );

  server.registerTool(
    "memory.get",
    {
      title: "Get project memory",
      description: "Fetch one memory by id.",
      inputSchema: {
        projectRoot: z.string(),
        id: z.number().int().positive()
      }
    },
    async ({ projectRoot, id }) => jsonResult(service.get(projectRoot, id))
  );

  server.registerTool(
    "memory.project_brief",
    {
      title: "Project memory brief",
      description: "Return compact conventions, decisions, pitfalls, and recent memories for a project.",
      inputSchema: {
        projectRoot: z.string()
      }
    },
    async ({ projectRoot }) => jsonResult(service.projectBrief(projectRoot))
  );

  server.registerTool(
    "memory.update",
    {
      title: "Update project memory",
      description: "Correct, refine, or archive an existing memory.",
      inputSchema: {
        projectRoot: z.string(),
        id: z.number().int().positive(),
        content: z.string().optional(),
        summary: z.string().optional(),
        whyUsefulLater: z.string().optional(),
        tags: z.array(z.string()).optional(),
        confidence: confidenceSchema.optional(),
        archive: z.boolean().optional(),
        reason: z.string().optional()
      }
    },
    async (input) => jsonResult(service.update(input))
  );

  server.registerTool(
    "memory.forget",
    {
      title: "Forget project memory",
      description: "Archive a memory by default, or hard delete when explicitly requested.",
      inputSchema: {
        projectRoot: z.string(),
        id: z.number().int().positive(),
        hardDelete: z.boolean().optional(),
        reason: z.string().optional()
      }
    },
    async (input) => jsonResult(service.forget(input))
  );

  server.registerTool(
    "memory.capture_task_summary",
    {
      title: "Capture durable task learnings",
      description: "Store reusable end-of-task learnings after quality checks.",
      inputSchema: {
        projectRoot: z.string(),
        taskSummary: z.string(),
        durableLearnings: z.array(z.string()),
        testsRun: z.array(z.string()).default([]),
        shouldRemember: z.boolean()
      }
    },
    async (input) => jsonResult(service.captureTaskSummary(input))
  );

  server.registerTool(
    "memory.export_project",
    {
      title: "Export project memory",
      description: "Export project memory for backup or migration.",
      inputSchema: {
        projectRoot: z.string(),
        includeArchived: z.boolean().optional()
      }
    },
    async ({ projectRoot, includeArchived }) => jsonResult(service.exportProject(projectRoot, includeArchived ?? false))
  );

  server.registerTool(
    "memory.import_project",
    {
      title: "Import project memory",
      description: "Import a project memory export with validation and deduplication.",
      inputSchema: {
        projectRoot: z.string(),
        exportJson: z.unknown()
      }
    },
    async ({ projectRoot, exportJson }) => jsonResult(service.importProject(projectRoot, exportJson))
  );

  server.registerTool(
    "memory.link_project_paths",
    {
      title: "Link project paths",
      description: "Explicitly link another checkout path to the same project memory.",
      inputSchema: {
        primaryProjectRoot: z.string(),
        additionalProjectRoot: z.string()
      }
    },
    async ({ primaryProjectRoot, additionalProjectRoot }) =>
      jsonResult(service.linkProjectPaths(primaryProjectRoot, additionalProjectRoot))
  );

  server.registerTool(
    "memory.possible_project_matches",
    {
      title: "Find possible project memory matches",
      description: "Find known paths with the same git remote fingerprint without merging them.",
      inputSchema: {
        projectRoot: z.string()
      }
    },
    async ({ projectRoot }) => jsonResult(service.possibleProjectMatches(projectRoot))
  );

  server.registerTool(
    "user.remember",
    {
      title: "Remember user knowledge",
      description:
        "Store durable, cross-project knowledge about the user — preferences, behaviors, context, workflows, conventions, tool choices, and communication style.",
      inputSchema: {
        kind: userMemoryKindSchema,
        content: z.string().describe("Specific durable memory content."),
        summary: z.string().optional(),
        whyUsefulLater: z.string().describe("Required by policy: why future agents will need this."),
        tags: z.array(z.string()).optional(),
        confidence: confidenceSchema.optional(),
        source: z.string().optional(),
        sourceRef: z.string().optional()
      }
    },
    async (input) => jsonResult(userService.remember(input))
  );

  server.registerTool(
    "user.search",
    {
      title: "Search user memory",
      description: "Search global user memory with optional kind and tag filters.",
      inputSchema: {
        query: z.string(),
        k: z.number().int().positive().max(25).optional(),
        kinds: z.array(userMemoryKindSchema).optional(),
        tags: z.array(z.string()).optional(),
        includeArchived: z.boolean().optional()
      }
    },
    async (input) => jsonResult(userService.search(input))
  );

  server.registerTool(
    "user.get",
    {
      title: "Get user memory",
      description: "Fetch one user memory by id.",
      inputSchema: {
        id: z.number().int().positive()
      }
    },
    async ({ id }) => jsonResult(userService.get(id))
  );

  server.registerTool(
    "user.brief",
    {
      title: "User memory brief",
      description:
        "Return compact preferences, behaviors, context, and recent user memories. Read this at session start to understand the user.",
      inputSchema: {}
    },
    async () => jsonResult(userService.brief())
  );

  server.registerTool(
    "user.update",
    {
      title: "Update user memory",
      description: "Correct, refine, or archive an existing user memory.",
      inputSchema: {
        id: z.number().int().positive(),
        content: z.string().optional(),
        summary: z.string().optional(),
        whyUsefulLater: z.string().optional(),
        tags: z.array(z.string()).optional(),
        confidence: confidenceSchema.optional(),
        archive: z.boolean().optional(),
        reason: z.string().optional()
      }
    },
    async (input) => jsonResult(userService.update(input))
  );

  server.registerTool(
    "user.forget",
    {
      title: "Forget user memory",
      description: "Archive a user memory by default, or hard delete when explicitly requested.",
      inputSchema: {
        id: z.number().int().positive(),
        hardDelete: z.boolean().optional(),
        reason: z.string().optional()
      }
    },
    async (input) => jsonResult(userService.forget(input))
  );

  server.registerTool(
    "user.export",
    {
      title: "Export user memory",
      description: "Export all user memory for backup or migration.",
      inputSchema: {
        includeArchived: z.boolean().optional()
      }
    },
    async ({ includeArchived }) => jsonResult(userService.export(includeArchived ?? false))
  );

  server.registerTool(
    "user.import",
    {
      title: "Import user memory",
      description: "Import a user memory export with validation and deduplication.",
      inputSchema: {
        exportJson: z.unknown()
      }
    },
    async ({ exportJson }) => jsonResult(userService.import(exportJson))
  );

  registerResource(server, "user-memory-brief", "memory://user/brief", () => userService.brief());
  registerResource(
    server,
    "user-memory-preferences",
    "memory://user/preferences",
    () => userService.brief().preferences
  );
  registerResource(server, "user-memory-behaviors", "memory://user/behaviors", () => userService.brief().behaviors);
  registerResource(server, "user-memory-context", "memory://user/context", () => userService.brief().context);

  server.registerPrompt(
    "user_memory_bootstrap",
    {
      title: "Bootstrap user memory",
      description: "Read user memory at the start of a session to understand preferences and context.",
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
      description: "Store durable user-level learnings observed during a session.",
      argsSchema: {
        sessionSummary: z.string().optional()
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

  registerResource(server, "project-memory-brief", "memory://project/current/brief", () =>
    service.projectBrief(currentProjectRoot())
  );
  registerResource(
    server,
    "project-memory-conventions",
    "memory://project/current/conventions",
    () => service.projectBrief(currentProjectRoot()).conventions
  );
  registerResource(
    server,
    "project-memory-decisions",
    "memory://project/current/decisions",
    () => service.projectBrief(currentProjectRoot()).decisions
  );
  registerResource(
    server,
    "project-memory-pitfalls",
    "memory://project/current/pitfalls",
    () => service.projectBrief(currentProjectRoot()).pitfalls
  );
  registerResource(
    server,
    "project-memory-recent",
    "memory://project/current/recent",
    () => service.projectBrief(currentProjectRoot()).recent
  );

  server.registerPrompt(
    "memory_bootstrap",
    {
      title: "Bootstrap project memory",
      description: "Fetch relevant memory before non-trivial project work.",
      argsSchema: {
        task: z.string().optional()
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
      description: "Store only durable learnings after a task.",
      argsSchema: {
        taskSummary: z.string(),
        testsRun: z.string().optional()
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
      description: "Review memory for stale, contradictory, or low-confidence entries.",
      argsSchema: {
        topic: z.string().optional()
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

function registerResource(server: McpServer, name: string, uri: string, read: () => unknown): void {
  server.registerResource(
    name,
    uri,
    {
      title: name,
      description: `Project memory resource ${uri}`,
      mimeType: "application/json"
    },
    async (resourceUri) => ({
      contents: [
        {
          uri: resourceUri.href,
          mimeType: "application/json",
          text: JSON.stringify(read(), null, 2)
        }
      ]
    })
  );
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
