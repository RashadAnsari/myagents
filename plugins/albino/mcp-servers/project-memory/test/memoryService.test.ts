import { mkdtempSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { Database } from "bun:sqlite";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "bun:test";
import { ProjectMemoryStore } from "../src/db.js";
import { MemoryQualityError, ProjectMemoryService, UserMemoryService } from "../src/memoryService.js";
import { defaultDatabasePath, normalizeProjectRoot } from "../src/paths.js";

let tempDir: string;
let store: ProjectMemoryStore;
let service: ProjectMemoryService;

beforeEach(() => {
  tempDir = mkdtempSync(path.join(tmpdir(), "project-memory-test-"));
  store = new ProjectMemoryStore(path.join(tempDir, "memory.sqlite"));
  service = new ProjectMemoryService(store);
});

afterEach(() => {
  store.close();
  rmSync(tempDir, { recursive: true, force: true });
});

describe("ProjectMemoryService", () => {
  it("stores and searches durable memory", () => {
    const memory = service.remember({
      projectRoot: tempDir,
      kind: "decision",
      content:
        "Use the project-memory MCP server for durable project decisions and verify memories against repo files before acting.",
      whyUsefulLater:
        "Future agents need this to retrieve useful project context without trusting stale notes blindly.",
      tags: ["mcp", "memory"],
      confidence: "high",
      source: "test"
    });

    const results = service.search({ projectRoot: tempDir, query: "durable project decisions", k: 5 });

    expect(memory.id).toBeGreaterThan(0);
    expect(results).toHaveLength(1);
    expect(results[0]?.content).toContain("durable project decisions");
  });

  it("filters search results by kind and tag", () => {
    service.remember({
      projectRoot: tempDir,
      kind: "decision",
      content:
        "Memory search should support decision filtering for architecture discussions about durable context retrieval.",
      whyUsefulLater: "Future agents need filtered retrieval when many memory kinds exist in the same project.",
      tags: ["architecture", "retrieval"],
      confidence: "high"
    });
    service.remember({
      projectRoot: tempDir,
      kind: "gotcha",
      content:
        "Memory search should also store gotchas about retrieval behavior without mixing them into decision results.",
      whyUsefulLater: "Future agents need gotcha filtering separately from durable architecture decisions.",
      tags: ["retrieval"],
      confidence: "medium"
    });

    const results = service.search({
      projectRoot: tempDir,
      query: "retrieval",
      kinds: ["decision"],
      tags: ["architecture"]
    });

    expect(results).toHaveLength(1);
    expect(results[0]?.kind).toBe("decision");
    expect(results[0]?.tags).toContain("architecture");
  });

  it("rejects vague automatic memory writes", () => {
    expect(() =>
      service.remember({
        projectRoot: tempDir,
        kind: "handoff",
        content: "fixed the issue",
        whyUsefulLater: "Useful later because this says what happened."
      })
    ).toThrow(MemoryQualityError);
  });

  it("rejects secret-looking memory writes", () => {
    expect(() =>
      service.remember({
        projectRoot: tempDir,
        kind: "preference",
        content: "The deployment API key is API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890 and should be reused.",
        whyUsefulLater: "Future agents would need this credential to deploy the project later."
      })
    ).toThrow(MemoryQualityError);
  });

  it("rejects command-output memories and duplicate memories", () => {
    const durableMemory = {
      projectRoot: tempDir,
      kind: "workflow" as const,
      content:
        "Agents should store durable workflow notes only when those notes change future implementation behavior.",
      whyUsefulLater: "Future agents need this workflow rule to avoid saving noisy task status as memory."
    };

    service.remember(durableMemory);

    expect(() => service.remember(durableMemory)).toThrow(MemoryQualityError);
    expect(() =>
      service.remember({
        projectRoot: tempDir,
        kind: "handoff",
        content: "npm test\npassed everything and there is no durable project learning here.",
        whyUsefulLater: "Future agents do not need raw command output as durable project knowledge."
      })
    ).toThrow(MemoryQualityError);
  });

  it("archives stale memory by default", () => {
    const memory = service.remember({
      projectRoot: tempDir,
      kind: "gotcha",
      content: "Old setup instructions require running the legacy memory worker before using project search.",
      whyUsefulLater: "Future agents may find old setup instructions and need to know they can become stale.",
      confidence: "medium"
    });

    const result = service.forget({
      projectRoot: tempDir,
      id: memory.id,
      reason: "The setup no longer uses a worker."
    });

    expect(result).toEqual({ archived: true, deleted: false });
    expect(service.search({ projectRoot: tempDir, query: "legacy memory worker" })).toHaveLength(0);
    expect(service.search({ projectRoot: tempDir, query: "legacy memory worker", includeArchived: true })).toHaveLength(
      1
    );
    expect(service.exportProject(tempDir, true).events.map((event) => event.action)).toEqual(["created", "forgotten"]);
  });

  it("updates memory content and rejects secret-looking updates", () => {
    const memory = service.remember({
      projectRoot: tempDir,
      kind: "convention",
      content:
        "Project memory updates should refine stored conventions when repo behavior proves an old note incomplete.",
      whyUsefulLater: "Future agents need corrected conventions when project behavior evolves over time.",
      confidence: "medium"
    });

    const updated = service.update({
      projectRoot: tempDir,
      id: memory.id,
      content:
        "Project memory updates should refine stored conventions when repo behavior proves an old note incomplete or stale.",
      confidence: "high",
      reason: "Clarified stale behavior."
    });

    expect(updated.confidence).toBe("high");
    expect(updated.content).toContain("stale");
    expect(() =>
      service.update({
        projectRoot: tempDir,
        id: memory.id,
        content: "The secret token is API_TOKEN=sk-abcdefghijklmnopqrstuvwxyz1234567890.",
        reason: "Bad update."
      })
    ).toThrow(MemoryQualityError);
  });

  it("keeps a project-scoped audit event after hard delete", () => {
    const memory = service.remember({
      projectRoot: tempDir,
      kind: "gotcha",
      content: "Temporary memory can be hard deleted when the user explicitly requests permanent removal.",
      whyUsefulLater: "Future agents need to preserve deletion behavior when maintaining memory privacy controls.",
      confidence: "medium"
    });

    const result = service.forget({
      projectRoot: tempDir,
      id: memory.id,
      hardDelete: true,
      reason: "Permanent deletion requested."
    });

    expect(result).toEqual({ archived: false, deleted: true });
    expect(service.exportProject(tempDir, true).events.map((event) => event.action)).toContain("hard_deleted");
  });

  it("exports and imports project memory", () => {
    service.remember({
      projectRoot: tempDir,
      kind: "architecture",
      content:
        "Project memory uses SQLite FTS search so agents can retrieve compact context before fetching full details.",
      whyUsefulLater: "Future agents need the retrieval architecture when extending or debugging the memory server.",
      confidence: "high"
    });

    const exportJson = service.exportProject(tempDir);
    const otherRoot = path.join(tempDir, "other-checkout");
    const result = service.importProject(otherRoot, exportJson);

    expect(result.imported).toBe(1);
    expect(service.search({ projectRoot: otherRoot, query: "SQLite FTS search" })).toHaveLength(1);
  });

  it("rejects malformed imports", () => {
    expect(() => service.importProject(tempDir, { memories: [] })).toThrow("Invalid project memory export shape.");
  });

  it("rejects imports with invalid memory record fields", () => {
    expect(() =>
      service.importProject(tempDir, {
        project: { rootPath: tempDir, name: "test" },
        memories: [{ kind: "bad-kind", content: "some content", whyUsefulLater: "reason" }],
        events: []
      })
    ).toThrow("Memory record has invalid kind");

    expect(() =>
      service.importProject(tempDir, {
        project: { rootPath: tempDir, name: "test" },
        memories: [{ kind: "decision", content: "", whyUsefulLater: "reason" }],
        events: []
      })
    ).toThrow("Memory record missing required content field");
  });

  it("blocks access to memory from a different project", () => {
    const otherRoot = path.join(tempDir, "other-project");
    const memory = service.remember({
      projectRoot: tempDir,
      kind: "decision",
      content: "Project ownership is enforced: memory from one project cannot be accessed by another project.",
      whyUsefulLater: "Future agents need isolation guarantees when multiple projects share the same memory store.",
      confidence: "high"
    });

    expect(() => service.get(otherRoot, memory.id)).toThrow("Memory not found for project");
    expect(() =>
      service.update({ projectRoot: otherRoot, id: memory.id, content: "cross-project tamper attempt content here" })
    ).toThrow("Memory not found for project");
    expect(() => service.forget({ projectRoot: otherRoot, id: memory.id })).toThrow("Memory not found for project");
  });

  it("normalizes tags to lowercase and drops tags with disallowed characters", () => {
    const memory = service.remember({
      projectRoot: tempDir,
      kind: "convention",
      content: "Tag validation normalizes tags to lowercase and drops tags that contain spaces or special characters.",
      whyUsefulLater: "Future agents need to know which tag formats are accepted to avoid silent data loss.",
      tags: ["valid-tag", "also_valid", "UPPERCASE", "has space", "has.dot"],
      confidence: "medium"
    });

    expect(memory.tags).toContain("valid-tag");
    expect(memory.tags).toContain("also_valid");
    expect(memory.tags).toContain("uppercase"); // lowercased and kept
    expect(memory.tags).not.toContain("UPPERCASE"); // original casing gone
    expect(memory.tags).not.toContain("has space"); // space not in [a-z0-9_-]
    expect(memory.tags).not.toContain("has.dot"); // dot not in [a-z0-9_-]
  });

  it("handles non-tokenizable queries gracefully by falling back to LIKE search", () => {
    service.remember({
      projectRoot: tempDir,
      kind: "gotcha",
      content: "Non-tokenizable queries such as emoji-only strings fall back to LIKE search without error.",
      whyUsefulLater: "Future agents need search to be resilient when users provide unusual or symbolic query strings.",
      confidence: "medium"
    });

    expect(() => service.search({ projectRoot: tempDir, query: "🔥" })).not.toThrow();
    // Single-char query produces no FTS terms, so falls back to LIKE and still matches
    const results = service.search({ projectRoot: tempDir, query: "e" });
    expect(results.length).toBeGreaterThan(0);
  });

  it("can update fields of an already-archived memory", () => {
    const memory = service.remember({
      projectRoot: tempDir,
      kind: "gotcha",
      content: "Archived memories remain updatable so their confidence and notes can be corrected before review.",
      whyUsefulLater: "Future agents need to correct stale archived memories when their content is partly inaccurate.",
      confidence: "low"
    });

    service.forget({ projectRoot: tempDir, id: memory.id, reason: "Archiving for test." });
    const updated = service.update({
      projectRoot: tempDir,
      id: memory.id,
      confidence: "high",
      reason: "Correcting confidence of archived memory."
    });

    expect(updated.confidence).toBe("high");
    expect(updated.archivedAt).not.toBeNull();
  });

  it("captures task summaries with partial skips", () => {
    const result = service.captureTaskSummary({
      projectRoot: tempDir,
      taskSummary: "Added project memory feature.",
      durableLearnings: [
        "Project memory durable task summaries should only retain learnings that future agents can reuse across related work.",
        "fixed the issue"
      ],
      testsRun: ["bun test"],
      shouldRemember: true
    });

    expect(result.stored).toHaveLength(1);
    expect(result.skipped).toHaveLength(1);
  });

  it("explicitly links project paths without implicit merging", () => {
    const otherRoot = path.join(tempDir, "other-checkout");
    const result = service.linkProjectPaths(tempDir, otherRoot);

    expect(result.knownPaths).toContain(path.resolve(tempDir));
    expect(result.knownPaths).toContain(path.resolve(otherRoot));
  });

  it("normalizes project roots", () => {
    expect(normalizeProjectRoot(path.join(tempDir, "..", path.basename(tempDir)))).toBe(path.resolve(tempDir));
  });

  it("migrates old event tables and backfills project ids", () => {
    const dbPath = path.join(tempDir, "old-memory.sqlite");
    const oldDb = new Database(dbPath);
    oldDb.exec(`
      CREATE TABLE projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        root_path TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        git_remote TEXT,
        remote_fingerprint TEXT,
        known_paths_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE TABLE memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        content TEXT NOT NULL,
        summary TEXT,
        why_useful_later TEXT NOT NULL,
        tags_json TEXT NOT NULL DEFAULT '[]',
        confidence TEXT NOT NULL DEFAULT 'medium',
        source TEXT,
        source_ref TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_used_at TEXT,
        use_count INTEGER NOT NULL DEFAULT 0,
        archived_at TEXT
      );
      CREATE TABLE memory_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        reason TEXT,
        created_at TEXT NOT NULL
      );
      INSERT INTO projects (root_path, name, known_paths_json, created_at, updated_at)
      VALUES ('${tempDir}', 'project', '["${tempDir}"]', '2026-01-01T00:00:00.000Z', '2026-01-01T00:00:00.000Z');
      INSERT INTO memories (project_id, kind, content, why_useful_later, created_at, updated_at)
      VALUES (1, 'decision', 'Old memory rows need event project id backfills during migration.', 'Future maintainers need migrations to preserve old audit rows.', '2026-01-01T00:00:00.000Z', '2026-01-01T00:00:00.000Z');
      INSERT INTO memory_events (memory_id, action, reason, created_at)
      VALUES (1, 'created', 'old event', '2026-01-01T00:00:00.000Z');
    `);
    oldDb.close();

    const migratedStore = new ProjectMemoryStore(dbPath);
    const migratedService = new ProjectMemoryService(migratedStore);

    expect(migratedService.exportProject(tempDir, true).events[0]?.projectId).toBe(1);

    migratedStore.close();
  });

  it("MYAGENTS_MEMORY_DIR override places database directly inside the specified directory", () => {
    const previous = process.env.MYAGENTS_MEMORY_DIR;
    process.env.MYAGENTS_MEMORY_DIR = path.join(tempDir, "override-memory");
    try {
      expect(defaultDatabasePath()).toBe(path.join(tempDir, "override-memory", "memory.sqlite"));
    } finally {
      if (previous === undefined) {
        delete process.env.MYAGENTS_MEMORY_DIR;
      } else {
        process.env.MYAGENTS_MEMORY_DIR = previous;
      }
    }
  });

  it("finds possible project matches for the same git remote without linking", () => {
    const firstRoot = path.join(tempDir, "first");
    const secondRoot = path.join(tempDir, "second");
    execFileSync("git", ["init", firstRoot], { stdio: "ignore" });
    execFileSync("git", ["-C", firstRoot, "remote", "add", "origin", "git@github.com:RashadAnsari/example.git"], {
      stdio: "ignore"
    });
    execFileSync("git", ["init", secondRoot], { stdio: "ignore" });
    execFileSync("git", ["-C", secondRoot, "remote", "add", "origin", "https://github.com/RashadAnsari/example.git"], {
      stdio: "ignore"
    });

    service.remember({
      projectRoot: firstRoot,
      kind: "decision",
      content: "Project match detection stores a remote fingerprint without merging checkout paths automatically.",
      whyUsefulLater: "Future agents need to detect related checkouts while avoiding unsafe automatic memory merges.",
      confidence: "high"
    });

    const matches = service.possibleProjectMatches(secondRoot);

    expect(matches.matches).toContain(path.resolve(firstRoot));
  });
});

let userStore: ProjectMemoryStore;
let userService: UserMemoryService;

beforeEach(() => {
  userStore = new ProjectMemoryStore(path.join(tempDir, "user-memory.sqlite"));
  userService = new UserMemoryService(userStore);
});

afterEach(() => {
  userStore.close();
});

describe("UserMemoryService", () => {
  it("stores and searches user memory", () => {
    const memory = userService.remember({
      kind: "preference",
      content:
        "The user consistently prefers TypeScript strict mode enabled in every project and expects explicit return types on all exported functions.",
      whyUsefulLater: "Future agents should enable strict mode and add return types without being asked each time.",
      tags: ["typescript", "style"],
      confidence: "high"
    });

    const results = userService.search({ query: "typescript strict mode" });

    expect(memory.id).toBeGreaterThan(0);
    expect(memory.kind).toBe("preference");
    expect(results).toHaveLength(1);
    expect(results[0]?.content).toContain("strict mode");
  });

  it("filters search by kind and tag", () => {
    userService.remember({
      kind: "preference",
      content:
        "User prefers dark-themed terminal output using ANSI color codes for all CLI tools and development scripts.",
      whyUsefulLater: "Agents should use dark-friendly colors when generating CLI output or scripts for this user.",
      tags: ["cli", "colors"],
      confidence: "medium"
    });
    userService.remember({
      kind: "behavior",
      content:
        "User habitually runs the full test suite before committing and expects agents to do the same before marking tasks complete.",
      whyUsefulLater: "Agents must run all tests before calling any task done to match the user's quality standard.",
      tags: ["testing"],
      confidence: "high"
    });

    const results = userService.search({ query: "colors output", kinds: ["preference"], tags: ["cli"] });

    expect(results).toHaveLength(1);
    expect(results[0]?.kind).toBe("preference");
    expect(results[0]?.tags).toContain("cli");
  });

  it("rejects vague user memory content", () => {
    expect(() =>
      userService.remember({
        kind: "behavior",
        content: "fixed the issue",
        whyUsefulLater: "Future agents need this to understand user behavior patterns well enough to act."
      })
    ).toThrow(MemoryQualityError);
  });

  it("rejects secret-looking user memory", () => {
    expect(() =>
      userService.remember({
        kind: "preference",
        content: "User prefers API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890 to be used for all OpenAI API requests.",
        whyUsefulLater: "Future agents need this credential to make API calls on behalf of the user."
      })
    ).toThrow(MemoryQualityError);
  });

  it("rejects command-output-looking user memory", () => {
    expect(() =>
      userService.remember({
        kind: "workflow",
        content: "npm test\npassed everything and there are no durable workflow learnings here for the user.",
        whyUsefulLater: "Future agents do not need raw command output as durable user knowledge."
      })
    ).toThrow(MemoryQualityError);
  });

  it("rejects duplicate user memory", () => {
    const input = {
      kind: "convention" as const,
      content:
        "User applies two-space indentation consistently across all TypeScript and JavaScript projects they work on.",
      whyUsefulLater: "Agents should use two-space indentation without asking when editing user files."
    };

    userService.remember(input);

    expect(() => userService.remember(input)).toThrow(MemoryQualityError);
  });

  it("archives user memory by default", () => {
    const memory = userService.remember({
      kind: "tool_preference",
      content:
        "User previously preferred the Yarn package manager for all Node.js projects over npm and pnpm alternatives.",
      whyUsefulLater: "Agents can check this when suggesting package manager commands for the user's projects.",
      confidence: "medium"
    });

    const result = userService.forget({ id: memory.id, reason: "User switched to pnpm." });

    expect(result).toEqual({ archived: true, deleted: false });
    expect(userService.search({ query: "Yarn package manager" })).toHaveLength(0);
    expect(userService.search({ query: "Yarn package manager", includeArchived: true })).toHaveLength(1);
  });

  it("hard-deletes user memory and keeps audit event", () => {
    const memory = userService.remember({
      kind: "context",
      content:
        "User is a senior backend engineer at Acme Corp working primarily on distributed systems and data pipelines.",
      whyUsefulLater: "Agents can use this context to calibrate explanation depth and domain-specific terminology.",
      confidence: "high"
    });

    const result = userService.forget({ id: memory.id, hardDelete: true, reason: "Privacy request." });
    const exported = userService.export(true);

    expect(result).toEqual({ archived: false, deleted: true });
    expect(exported.memories).toHaveLength(0);
    expect(exported.events.map((e) => e.action)).toContain("hard_deleted");
  });

  it("exports and imports user memory", () => {
    userService.remember({
      kind: "communication",
      content:
        "User prefers concise, bullet-point explanations rather than long prose paragraphs when receiving technical summaries.",
      whyUsefulLater:
        "Agents should default to bullet points for technical summaries to match user communication style.",
      confidence: "high"
    });

    const exported = userService.export();
    const newStore = new ProjectMemoryStore(path.join(tempDir, "user-import-target.sqlite"));
    const newService = new UserMemoryService(newStore);
    const result = newService.import(exported);

    expect(result.imported).toBe(1);
    expect(newService.search({ query: "bullet-point summaries" })).toHaveLength(1);
    newStore.close();
  });

  it("rejects malformed user memory import", () => {
    expect(() => userService.import({ memories: [] })).toThrow("Invalid user memory export shape.");
    expect(() => userService.import({ events: [] })).toThrow("Invalid user memory export shape.");
  });

  it("rejects user memory import with invalid kind", () => {
    expect(() =>
      userService.import({
        memories: [{ kind: "bad-kind", content: "some content", whyUsefulLater: "reason" }],
        events: []
      })
    ).toThrow("Memory record has invalid kind");
  });

  it("rejects user memory import with missing required fields", () => {
    expect(() =>
      userService.import({
        memories: [{ kind: "preference", content: "", whyUsefulLater: "reason" }],
        events: []
      })
    ).toThrow("Memory record missing required content field");

    expect(() =>
      userService.import({
        memories: [{ kind: "preference", content: "some valid content here for the test", whyUsefulLater: "" }],
        events: []
      })
    ).toThrow("Memory record missing required whyUsefulLater field");
  });

  it("returns brief with correct category groupings", () => {
    userService.remember({
      kind: "preference",
      content:
        "User strongly prefers functional programming patterns over object-oriented class hierarchies in all TypeScript code.",
      whyUsefulLater: "Agents should use functional style by default without waiting for the user to request it.",
      confidence: "high"
    });
    userService.remember({
      kind: "behavior",
      content:
        "User consistently opens a scratch file to prototype ideas before writing production code in any codebase.",
      whyUsefulLater: "Agents should suggest a scratch file when the user seems to be in exploratory mode.",
      confidence: "medium"
    });
    userService.remember({
      kind: "context",
      content:
        "User works as a principal engineer at a fintech startup where correctness and auditability are top priorities.",
      whyUsefulLater: "Agents should emphasize correctness, testing, and audit trails when advising this user.",
      confidence: "high"
    });

    const brief = userService.brief();

    expect(brief.preferences.map((m) => m.kind)).toContain("preference");
    expect(brief.behaviors.map((m) => m.kind)).toContain("behavior");
    expect(brief.context.map((m) => m.kind)).toContain("context");
    expect(brief.recent.length).toBeGreaterThan(0);
  });

  it("update corrects content and rejects secret updates", () => {
    const memory = userService.remember({
      kind: "workflow",
      content:
        "User always reviews the full diff before merging pull requests and expects agents to summarize changes clearly.",
      whyUsefulLater: "Agents should surface clear change summaries so the user can review them before merging.",
      confidence: "medium"
    });

    const updated = userService.update({
      id: memory.id,
      content:
        "User always reviews the full diff before merging pull requests and expects agents to summarize changes in bullet points.",
      confidence: "high",
      reason: "More specific about format."
    });

    expect(updated.confidence).toBe("high");
    expect(updated.content).toContain("bullet points");

    expect(() =>
      userService.update({
        id: memory.id,
        content: "The secret token is API_TOKEN=sk-abcdefghijklmnopqrstuvwxyz1234567890.",
        reason: "Bad update."
      })
    ).toThrow(MemoryQualityError);
  });

  it("throws when getting or updating a non-existent user memory", () => {
    expect(() => userService.get(99999)).toThrow("User memory not found");
    expect(() => userService.update({ id: 99999, reason: "test" })).toThrow("User memory not found");
    expect(() => userService.forget({ id: 99999 })).toThrow("User memory not found");
  });

  it("normalizes tags to lowercase and drops disallowed characters", () => {
    const memory = userService.remember({
      kind: "convention",
      content:
        "User applies kebab-case naming for all CSS class names and file names across every front-end project they work on.",
      whyUsefulLater: "Agents should use kebab-case without asking when creating CSS or naming front-end files.",
      tags: ["CSS", "naming-conv", "FRONTEND", "has space", "has.dot"]
    });

    expect(memory.tags).toContain("css");
    expect(memory.tags).toContain("naming-conv");
    expect(memory.tags).toContain("frontend");
    expect(memory.tags).not.toContain("CSS");
    expect(memory.tags).not.toContain("has space");
    expect(memory.tags).not.toContain("has.dot");
  });

  it("handles non-tokenizable queries without error via LIKE fallback", () => {
    userService.remember({
      kind: "preference",
      content:
        "User prefers emoji-free output in all terminal and chat responses because they use a terminal without proper emoji support.",
      whyUsefulLater: "Agents should avoid emojis in terminal output and chat responses for this user.",
      confidence: "medium"
    });

    expect(() => userService.search({ query: "🔥" })).not.toThrow();
    const results = userService.search({ query: "e" });
    expect(results.length).toBeGreaterThan(0);
  });

  it("can update an already-archived user memory", () => {
    const memory = userService.remember({
      kind: "behavior",
      content:
        "User sometimes skips writing tests for utility functions but expects tests for all business logic paths.",
      whyUsefulLater: "Agents can prioritize test coverage for business logic and deprioritize pure utilities.",
      confidence: "low"
    });

    userService.forget({ id: memory.id, reason: "Archiving for test." });
    const updated = userService.update({ id: memory.id, confidence: "high", reason: "Correcting confidence." });

    expect(updated.confidence).toBe("high");
    expect(updated.archivedAt).not.toBeNull();
  });

  it("skips low-quality entries during import and counts them as skipped", () => {
    const exported = {
      exportedAt: new Date().toISOString(),
      memories: [
        {
          id: 1,
          kind: "preference",
          content:
            "User prefers TypeScript over JavaScript for all new projects due to the type safety and IDE support it provides.",
          whyUsefulLater: "Agents should default to TypeScript without asking for this user.",
          tags: [],
          confidence: "high",
          summary: null,
          source: null,
          sourceRef: null,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          lastUsedAt: null,
          useCount: 0,
          archivedAt: null
        },
        {
          id: 2,
          kind: "behavior",
          content: "fixed the issue",
          whyUsefulLater: "something",
          tags: [],
          confidence: "low",
          summary: null,
          source: null,
          sourceRef: null,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          lastUsedAt: null,
          useCount: 0,
          archivedAt: null
        }
      ],
      events: []
    };

    const result = userService.import(exported);

    expect(result.imported).toBe(1);
    expect(result.skipped).toBe(1);
  });
});
