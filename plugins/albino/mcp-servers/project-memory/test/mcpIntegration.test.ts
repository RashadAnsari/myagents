import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "bun:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { ProjectMemoryStore } from "../src/db.js";
import { ProjectMemoryService, UserMemoryService } from "../src/memoryService.js";
import { createProjectMemoryServer } from "../src/server.js";

let tempDir: string;
let store: ProjectMemoryStore;
let client: Client;

beforeEach(async () => {
  tempDir = mkdtempSync(path.join(tmpdir(), "project-memory-mcp-test-"));
  store = new ProjectMemoryStore(path.join(tempDir, "memory.sqlite"));
  const service = new ProjectMemoryService(store);
  const userService = new UserMemoryService(store);
  const server = createProjectMemoryServer(service, userService);
  client = new Client({ name: "project-memory-test", version: "0.0.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
});

afterEach(async () => {
  await client.close();
  store.close();
  rmSync(tempDir, { recursive: true, force: true });
});

describe("Project memory MCP integration", () => {
  it("exposes expected project tools, resources, and prompts", async () => {
    const tools = await client.listTools();
    const resources = await client.listResources();
    const prompts = await client.listPrompts();
    const toolNames = tools.tools.map((t) => t.name);
    const resourceUris = resources.resources.map((r) => r.uri);
    const promptNames = prompts.prompts.map((p) => p.name);

    expect(toolNames).toContain("memory.remember");
    expect(toolNames).toContain("memory.search");
    expect(toolNames).toContain("memory.get");
    expect(toolNames).toContain("memory.project_brief");
    expect(toolNames).toContain("memory.update");
    expect(toolNames).toContain("memory.forget");
    expect(toolNames).toContain("memory.capture_task_summary");
    expect(toolNames).toContain("memory.export_project");
    expect(toolNames).toContain("memory.import_project");
    expect(toolNames).toContain("memory.link_project_paths");
    expect(toolNames).toContain("memory.possible_project_matches");

    expect(resourceUris).toContain("memory://project/current/brief");
    expect(resourceUris).toContain("memory://project/current/conventions");
    expect(resourceUris).toContain("memory://project/current/decisions");
    expect(resourceUris).toContain("memory://project/current/pitfalls");
    expect(resourceUris).toContain("memory://project/current/recent");

    expect(promptNames).toContain("memory_bootstrap");
    expect(promptNames).toContain("memory_handoff");
    expect(promptNames).toContain("memory_cleanup");
  });

  it("exposes expected user tools, resources, and prompts", async () => {
    const tools = await client.listTools();
    const resources = await client.listResources();
    const prompts = await client.listPrompts();
    const toolNames = tools.tools.map((t) => t.name);
    const resourceUris = resources.resources.map((r) => r.uri);
    const promptNames = prompts.prompts.map((p) => p.name);

    expect(toolNames).toContain("user.remember");
    expect(toolNames).toContain("user.search");
    expect(toolNames).toContain("user.get");
    expect(toolNames).toContain("user.brief");
    expect(toolNames).toContain("user.update");
    expect(toolNames).toContain("user.forget");
    expect(toolNames).toContain("user.export");
    expect(toolNames).toContain("user.import");

    expect(resourceUris).toContain("memory://user/brief");
    expect(resourceUris).toContain("memory://user/preferences");
    expect(resourceUris).toContain("memory://user/behaviors");
    expect(resourceUris).toContain("memory://user/context");

    expect(promptNames).toContain("user_memory_bootstrap");
    expect(promptNames).toContain("user_memory_update");
  });

  it("stores and retrieves memory through MCP tool calls", async () => {
    const rememberResult = await client.callTool({
      name: "memory.remember",
      arguments: {
        projectRoot: tempDir,
        kind: "decision",
        content:
          "MCP integration tests should verify tool calls through the protocol rather than only service methods.",
        whyUsefulLater: "Future maintainers need protocol-level coverage when changing MCP server registration.",
        tags: ["mcp", "test"],
        confidence: "high"
      }
    });
    const remembered = JSON.parse(textContent(rememberResult));

    const searchResult = await client.callTool({
      name: "memory.search",
      arguments: {
        projectRoot: tempDir,
        query: "protocol coverage",
        k: 5
      }
    });
    const matches = JSON.parse(textContent(searchResult));

    expect(remembered.id).toBeGreaterThan(0);
    expect(matches).toHaveLength(1);
    expect(matches[0].tags).toContain("mcp");
  });

  it("returns tool errors for rejected low-quality memory", async () => {
    const result = await client.callTool({
      name: "memory.remember",
      arguments: {
        projectRoot: tempDir,
        kind: "handoff",
        content: "fixed the issue",
        whyUsefulLater: "Useful later because this says what happened."
      }
    });

    expect(result.isError).toBe(true);
    expect(textContent(result)).toContain("Memory content is too short");
  });

  it("reads resources and gets prompts through MCP", async () => {
    await client.callTool({
      name: "memory.remember",
      arguments: {
        projectRoot: process.cwd(),
        kind: "convention",
        content: "Resource tests should read the project memory brief through the MCP resource interface.",
        whyUsefulLater: "Future maintainers need resource coverage when changing MCP server registration.",
        tags: ["resource"],
        confidence: "high"
      }
    });

    const resource = await client.readResource({ uri: "memory://project/current/brief" });
    const prompt = await client.getPrompt({
      name: "memory_bootstrap",
      arguments: { task: "Review project memory coverage" }
    });

    expect(resource.contents[0]).toHaveProperty("text");
    const resourceText = "text" in resource.contents[0] ? resource.contents[0].text : "";
    expect(resourceText).toContain("conventions");
    expect(prompt.messages[0]?.content.type).toBe("text");
    expect(prompt.messages[0]?.content.type === "text" ? prompt.messages[0].content.text : "").toContain(
      "Review project memory coverage"
    );
  });

  it("stores and retrieves user memory through MCP tool calls", async () => {
    const rememberResult = await client.callTool({
      name: "user.remember",
      arguments: {
        kind: "preference",
        content:
          "User prefers verbose commit messages that explain the why behind changes rather than just the what was done.",
        whyUsefulLater:
          "Agents should write detailed commit messages explaining reasoning rather than just listing changes.",
        tags: ["git", "commits"],
        confidence: "high"
      }
    });
    const remembered = JSON.parse(textContent(rememberResult));

    const searchResult = await client.callTool({
      name: "user.search",
      arguments: { query: "commit messages why reasoning", k: 5 }
    });
    const matches = JSON.parse(textContent(searchResult));

    expect(remembered.id).toBeGreaterThan(0);
    expect(remembered.kind).toBe("preference");
    expect(matches).toHaveLength(1);
    expect(matches[0].tags).toContain("git");
  });

  it("returns tool error for rejected low-quality user memory", async () => {
    const result = await client.callTool({
      name: "user.remember",
      arguments: {
        kind: "behavior",
        content: "fixed the issue",
        whyUsefulLater: "Useful later."
      }
    });

    expect(result.isError).toBe(true);
    expect(textContent(result)).toContain("Memory content is too short");
  });

  it("user.get fetches a stored user memory by id", async () => {
    const rememberResult = await client.callTool({
      name: "user.remember",
      arguments: {
        kind: "context",
        content:
          "User is a full-stack developer with ten years of experience specializing in TypeScript and distributed systems.",
        whyUsefulLater: "Agents can calibrate explanation depth and suggest appropriate abstractions for this user.",
        confidence: "high"
      }
    });
    const remembered = JSON.parse(textContent(rememberResult));

    const getResult = await client.callTool({ name: "user.get", arguments: { id: remembered.id } });
    const fetched = JSON.parse(textContent(getResult));

    expect(fetched.id).toBe(remembered.id);
    expect(fetched.kind).toBe("context");
  });

  it("user.update modifies a user memory", async () => {
    const rememberResult = await client.callTool({
      name: "user.remember",
      arguments: {
        kind: "tool_preference",
        content:
          "User strongly prefers Visual Studio Code as their primary editor over other IDEs for all development work.",
        whyUsefulLater: "Agents should suggest VS Code extensions and shortcuts rather than alternatives.",
        confidence: "medium"
      }
    });
    const remembered = JSON.parse(textContent(rememberResult));

    const updateResult = await client.callTool({
      name: "user.update",
      arguments: { id: remembered.id, confidence: "high", reason: "User confirmed this is still accurate." }
    });
    const updated = JSON.parse(textContent(updateResult));

    expect(updated.confidence).toBe("high");
  });

  it("user.forget archives a user memory", async () => {
    const rememberResult = await client.callTool({
      name: "user.remember",
      arguments: {
        kind: "workflow",
        content:
          "User prefers to work in short focused sessions of ninety minutes followed by a break before switching tasks.",
        whyUsefulLater: "Agents should avoid scheduling long uninterrupted tasks when planning work for this user.",
        confidence: "medium"
      }
    });
    const remembered = JSON.parse(textContent(rememberResult));

    const forgetResult = await client.callTool({
      name: "user.forget",
      arguments: { id: remembered.id, reason: "Outdated workflow preference." }
    });
    const forgotten = JSON.parse(textContent(forgetResult));

    expect(forgotten.archived).toBe(true);
    expect(forgotten.deleted).toBe(false);
  });

  it("reads user memory brief resource and invokes user memory prompts", async () => {
    await client.callTool({
      name: "user.remember",
      arguments: {
        kind: "communication",
        content:
          "User prefers responses structured with clear headers and short sections rather than long unbroken prose blocks.",
        whyUsefulLater: "Agents should structure responses with headers and short sections for this user.",
        confidence: "high"
      }
    });

    const resource = await client.readResource({ uri: "memory://user/brief" });
    const bootstrap = await client.getPrompt({ name: "user_memory_bootstrap", arguments: {} });
    const update = await client.getPrompt({
      name: "user_memory_update",
      arguments: { sessionSummary: "Helped user refactor auth module." }
    });

    expect(resource.contents[0]).toHaveProperty("text");
    const briefText = "text" in resource.contents[0] ? resource.contents[0].text : "";
    expect(briefText).toContain("preferences");

    expect(bootstrap.messages[0]?.content.type).toBe("text");
    const bootstrapText = bootstrap.messages[0]?.content.type === "text" ? bootstrap.messages[0].content.text : "";
    expect(bootstrapText).toContain("memory://user/brief");

    expect(update.messages[0]?.content.type).toBe("text");
    const updateText = update.messages[0]?.content.type === "text" ? update.messages[0].content.text : "";
    expect(updateText).toContain("Helped user refactor auth module");
  });

  it("user.export and user.import round-trip through MCP", async () => {
    await client.callTool({
      name: "user.remember",
      arguments: {
        kind: "convention",
        content:
          "User applies the single responsibility principle strictly and prefers small composable functions over large monolithic implementations.",
        whyUsefulLater:
          "Agents should suggest breaking down large functions when reviewing or writing code for this user.",
        confidence: "high"
      }
    });

    const exportResult = await client.callTool({ name: "user.export", arguments: {} });
    const exported = JSON.parse(textContent(exportResult));
    expect(exported.memories).toHaveLength(1);

    const importResult = await client.callTool({ name: "user.import", arguments: { exportJson: exported } });
    const importSummary = JSON.parse(textContent(importResult));
    expect(importSummary.skipped).toBe(1); // duplicate skipped
  });
});

function textContent(result: unknown): string {
  const content = (result as { content?: Array<{ type: string; text?: string }> }).content ?? [];
  return content.find((item) => item.type === "text")?.text ?? "";
}
