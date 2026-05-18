import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "bun:test";

import { ProjectMemoryStore } from "../src/db.js";
import { ProjectMemoryService, UserMemoryService } from "../src/memoryService.js";
import { EMBEDDING_DIM, cosineSimilarity, embed, memoryEmbedText } from "../src/embedding.js";

let tempDir: string;
let store: ProjectMemoryStore;
let service: ProjectMemoryService;

beforeEach(() => {
  tempDir = mkdtempSync(path.join(tmpdir(), "vector-search-test-"));
  store = new ProjectMemoryStore(path.join(tempDir, "memory.sqlite"));
  service = new ProjectMemoryService(store);
});

afterEach(() => {
  store.close();
  rmSync(tempDir, { recursive: true, force: true });
});

describe("embedding module", () => {
  it("embed returns a 384-dim vector per input text", async () => {
    const vecs = await embed(["hello world"]);
    expect(vecs).toHaveLength(1);
    expect(vecs[0]).toHaveLength(EMBEDDING_DIM);
  });

  it("embed returns the same vector for the same text on repeated calls", async () => {
    const a = await embed(["hello world"]);
    const b = await embed(["hello world"]);
    // Real model is deterministic for the same input
    expect(a[0]!.length).toBe(EMBEDDING_DIM);
    expect(b[0]!.length).toBe(EMBEDDING_DIM);
    // Cosine similarity of the same text embedded twice should be ~1
    expect(cosineSimilarity(a[0]!, b[0]!)).toBeCloseTo(1, 4);
  });

  it("cosine similarity of identical vectors is 1", async () => {
    const vecs = await embed(["hello world test"]);
    const v = vecs[0]!;
    expect(cosineSimilarity(v, v)).toBeCloseTo(1, 4);
  });

  it("cosine similarity of semantically different texts is less than 1", async () => {
    const vecs = await embed(["relational database SQL query optimization", "CSS styling BEM methodology naming"]);
    const a = vecs[0]!;
    const b = vecs[1]!;
    const sim = cosineSimilarity(a, b);
    expect(sim).toBeLessThan(1);
  });

  it("memoryEmbedText concatenates content, summary, and tags", () => {
    const text = memoryEmbedText("main content here", "short summary", ["tag1", "tag2"]);
    expect(text).toContain("main content here");
    expect(text).toContain("short summary");
    expect(text).toContain("tag1");
    expect(text).toContain("tag2");
  });

  it("EMBEDDING_DIM is 384", () => {
    expect(EMBEDDING_DIM).toBe(384);
  });

  it("embed returns empty array for empty input", async () => {
    const vecs = await embed([]);
    expect(vecs).toHaveLength(0);
  });

  it("embed handles multiple texts in one batch", async () => {
    const vecs = await embed(["first sentence about databases", "second sentence about styling"]);
    expect(vecs).toHaveLength(2);
    expect(vecs[0]).toHaveLength(EMBEDDING_DIM);
    expect(vecs[1]).toHaveLength(EMBEDDING_DIM);
  });

  it("cosineSimilarity returns 0 for a zero vector", () => {
    const zero = new Array(EMBEDDING_DIM).fill(0);
    const nonZero = new Array(EMBEDDING_DIM).fill(0.1);
    expect(cosineSimilarity(zero, nonZero)).toBe(0);
    expect(cosineSimilarity(nonZero, zero)).toBe(0);
  });
});

describe("vector search — project memories", () => {
  it("stores an embedding for each memory created", async () => {
    await service.remember({
      projectRoot: tempDir,
      kind: "decision",
      content:
        "Project memory uses SQLite as its storage backend for durable and portable local persistence across sessions.",
      whyUsefulLater: "Future agents need to know the storage layer to diagnose database issues correctly.",
      confidence: "high"
    });

    // Verify embedding table is populated by doing a vector search
    const results = await service.search({ projectRoot: tempDir, query: "SQLite storage database persistence" });
    expect(results).toHaveLength(1);
  });

  it("vector search returns results in some order", async () => {
    await service.remember({
      projectRoot: tempDir,
      kind: "architecture",
      content:
        "The project uses a PostgreSQL relational database with connection pooling and prepared statement caching.",
      whyUsefulLater: "Future agents need to know the database backend to generate correct queries.",
      confidence: "high"
    });
    await service.remember({
      projectRoot: tempDir,
      kind: "convention",
      content:
        "All CSS class names follow BEM notation: block__element--modifier for consistent styling across components.",
      whyUsefulLater: "Future agents must use BEM notation when writing CSS to match the existing codebase style.",
      confidence: "high"
    });

    const results = await service.search({ projectRoot: tempDir, query: "database connection pool", k: 5 });
    expect(results.length).toBeGreaterThan(0);
  });

  it("vector search returns results for matching content", async () => {
    await service.remember({
      projectRoot: tempDir,
      kind: "gotcha",
      content:
        "When deploying to production, always run database migration scripts before restarting application servers.",
      whyUsefulLater: "Future agents need this ordering rule to avoid application startup failures during deployments.",
      confidence: "high"
    });

    const results = await service.search({ projectRoot: tempDir, query: "migration deployment ordering" });
    expect(results).toHaveLength(1);
    expect(results[0]?.content).toContain("migration");
  });

  it("does not return archived memories in default vector search", async () => {
    const memory = await service.remember({
      projectRoot: tempDir,
      kind: "convention",
      content:
        "Old convention: always use tabs for indentation in TypeScript files before the project standardized on spaces.",
      whyUsefulLater: "Future agents need to know this was the old convention before the migration to spaces.",
      confidence: "medium"
    });

    service.forget({ projectRoot: tempDir, id: memory.id, reason: "Convention changed to spaces." });

    // Vector search should not find it (embedding was removed on archive)
    const results = await service.search({ projectRoot: tempDir, query: "indentation TypeScript tabs" });
    expect(results).toHaveLength(0);

    // LIKE search via includeArchived=true should find it using a substring of the content
    const withArchived = await service.search({
      projectRoot: tempDir,
      query: "tabs for indentation",
      includeArchived: true
    });
    expect(withArchived.length).toBeGreaterThan(0);
  });

  it("backfills embeddings on store open for existing memories without embeddings", async () => {
    await service.remember({
      projectRoot: tempDir,
      kind: "decision",
      content:
        "Embedding backfill runs on startup to ensure existing memories gain vector representations automatically.",
      whyUsefulLater: "Future agents rely on vector search working even on pre-existing memory databases.",
      confidence: "high"
    });

    store.close();

    const newStore = new ProjectMemoryStore(path.join(tempDir, "memory.sqlite"));
    const newService = new ProjectMemoryService(newStore);
    // Async backfill via backfillEmbeddings
    await newService.backfillEmbeddings();

    const results = await newService.search({ projectRoot: tempDir, query: "backfill embeddings startup" });
    expect(results.length).toBeGreaterThan(0);

    newStore.close();
  });

  it("vector search ranks by cosine distance (semantically matching memory ranked first)", async () => {
    const mem1 = await service.remember({
      projectRoot: tempDir,
      kind: "architecture",
      content: "Alpha architecture memory about relational databases and SQL query optimization techniques.",
      whyUsefulLater: "Future agents need this for database query design.",
      confidence: "high"
    });
    await service.remember({
      projectRoot: tempDir,
      kind: "convention",
      content: "Beta convention memory about CSS styling patterns and BEM methodology naming conventions.",
      whyUsefulLater: "Future agents need this for CSS class naming.",
      confidence: "high"
    });

    const results = await service.search({
      projectRoot: tempDir,
      query: "relational database SQL query optimization",
      k: 5
    });

    expect(results.length).toBeGreaterThan(0);
    expect(results[0]?.id).toBe(mem1.id);
  });

  it("vector search finds semantically related memory with zero word overlap", async () => {
    // No words in this content appear in the query below
    const authMem = await service.remember({
      projectRoot: tempDir,
      kind: "gotcha",
      content:
        "Authentication fails with JWT tokens expiring too early because the server clock and client clock are not synchronized across timezone boundaries.",
      whyUsefulLater: "Future agents need this to diagnose silent credential rejections during deployment windows.",
      confidence: "high"
    });
    await service.remember({
      projectRoot: tempDir,
      kind: "convention",
      content: "All React components use functional style with hooks exclusively, class components are prohibited.",
      whyUsefulLater: "Future agents must write functional components and avoid class syntax in this codebase.",
      confidence: "high"
    });

    // Query shares zero words with the auth memory content above
    const results = await service.search({
      projectRoot: tempDir,
      query: "login issue session timeout",
      k: 5
    });

    expect(results.length).toBeGreaterThan(0);
    expect(results[0]?.id).toBe(authMem.id);
  });

  it("vector search on empty corpus returns empty array", async () => {
    const results = await service.search({ projectRoot: tempDir, query: "anything at all" });
    expect(results).toHaveLength(0);
  });

  it("vector search respects the k limit", async () => {
    const contents = [
      "First memory about deployment pipelines and continuous integration workflows in the project.",
      "Second memory about database schema design and migration strategies for production releases.",
      "Third memory about API versioning conventions and backward compatibility requirements.",
      "Fourth memory about frontend build tooling configuration and webpack optimization settings.",
      "Fifth memory about error handling conventions and structured logging format requirements."
    ];
    for (const content of contents) {
      await service.remember({
        projectRoot: tempDir,
        kind: "convention",
        content,
        whyUsefulLater: "Future agents need this convention for consistent implementation across the project.",
        confidence: "medium"
      });
    }

    const results = await service.search({ projectRoot: tempDir, query: "project conventions standards", k: 2 });
    expect(results).toHaveLength(2);
  });
});

describe("vector search — user memories", () => {
  let userStore: ProjectMemoryStore;
  let userService: UserMemoryService;

  beforeEach(() => {
    userStore = new ProjectMemoryStore(path.join(tempDir, "user-memory.sqlite"));
    userService = new UserMemoryService(userStore);
  });

  afterEach(() => {
    userStore.close();
  });

  it("stores an embedding for each user memory created", async () => {
    await userService.remember({
      kind: "preference",
      content:
        "User strongly prefers concise function names that accurately describe what the function does without abbreviation.",
      whyUsefulLater: "Agents should avoid abbreviated function names and prefer clarity when naming functions.",
      confidence: "high"
    });

    const results = await userService.search({ query: "naming functions concise clarity" });
    expect(results).toHaveLength(1);
  });

  it("vector search returns the most relevant user memory", async () => {
    await userService.remember({
      kind: "preference",
      content: "User prefers test-driven development and writes failing tests before implementing any production code.",
      whyUsefulLater: "Agents should write tests first and treat failing tests as the starting point for all features.",
      confidence: "high"
    });
    await userService.remember({
      kind: "convention",
      content: "User applies kebab-case naming for all file names in frontend projects without exception.",
      whyUsefulLater: "Agents should name files in kebab-case when creating frontend project files.",
      confidence: "high"
    });

    const results = await userService.search({ query: "tests driven development TDD failing first" });
    expect(results.length).toBeGreaterThan(0);
    expect(results[0]?.content).toContain("test");
  });

  it("does not return archived user memories in default vector search", async () => {
    const memory = await userService.remember({
      kind: "tool_preference",
      content:
        "User previously used Yarn for package management but has since migrated all projects to pnpm for better performance.",
      whyUsefulLater: "Agents should use pnpm and not suggest Yarn for this user's projects.",
      confidence: "high"
    });

    userService.forget({ id: memory.id, reason: "Already migrated to pnpm." });

    const results = await userService.search({ query: "Yarn package management migration" });
    expect(results).toHaveLength(0);
  });
});
