import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "bun:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { ProjectMemoryStore } from "../src/db.js";
import { ProjectMemoryService } from "../src/memoryService.js";
import { createProjectMemoryServer } from "../src/server.js";

let tempDir: string;
let store: ProjectMemoryStore;
let client: Client;

beforeEach(async () => {
  tempDir = mkdtempSync(path.join(tmpdir(), "project-memory-mcp-test-"));
  store = new ProjectMemoryStore(path.join(tempDir, "memory.sqlite"));
  const service = new ProjectMemoryService(store);
  const server = createProjectMemoryServer(service);
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
  it("exposes expected tools, resources, and prompts", async () => {
    const tools = await client.listTools();
    const resources = await client.listResources();
    const prompts = await client.listPrompts();

    expect(tools.tools.map((tool) => tool.name)).toContain("memory.remember");
    expect(tools.tools.map((tool) => tool.name)).toContain("memory.search");
    expect(resources.resources.map((resource) => resource.uri)).toContain("memory://project/current/brief");
    expect(prompts.prompts.map((prompt) => prompt.name)).toContain("memory_bootstrap");
    expect(prompts.prompts.map((prompt) => prompt.name)).toContain("memory_handoff");
    expect(prompts.prompts.map((prompt) => prompt.name)).toContain("memory_cleanup");
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
});

function textContent(result: unknown): string {
  const content = (result as { content?: Array<{ type: string; text?: string }> }).content ?? [];
  return content.find((item) => item.type === "text")?.text ?? "";
}
