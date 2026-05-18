import { fingerprintRemote, getGitRemote, normalizeProjectRoot } from "./paths.js";
import { evaluateMemoryQuality, evaluateUserMemoryQuality, looksLikeSecret } from "./quality.js";
import { memoryKinds, userMemoryKinds } from "./types.js";
import type {
  Confidence,
  MemoryRecord,
  ProjectExport,
  RememberInput,
  SearchInput,
  UserMemoryExport,
  UserMemoryRecord,
  UserRememberInput,
  UserSearchInput
} from "./types.js";
import { ProjectMemoryStore } from "./db.js";
import { embed, memoryEmbedText } from "./embedding.js";

export class MemoryQualityError extends Error {
  constructor(readonly reasons: string[]) {
    super(`Memory rejected: ${reasons.join(" ")}`);
  }
}

export class ProjectMemoryService {
  constructor(private readonly store: ProjectMemoryStore) {}

  async remember(input: RememberInput): Promise<MemoryRecord> {
    const project = this.store.getOrCreateProject(input.projectRoot);
    const existing = this.store.listActiveMemories(project.id);
    const quality = evaluateMemoryQuality(input, existing);
    if (!quality.ok) {
      throw new MemoryQualityError(quality.reasons);
    }

    const tags = normalizeTags(input.tags);
    const memory = this.store.createMemory({
      projectId: project.id,
      kind: input.kind,
      content: input.content.trim(),
      summary: cleanOptional(input.summary),
      whyUsefulLater: input.whyUsefulLater?.trim() ?? "",
      tags,
      confidence: input.confidence ?? "medium",
      source: cleanOptional(input.source),
      sourceRef: cleanOptional(input.sourceRef)
    });

    try {
      const text = memoryEmbedText(memory.content, memory.summary, memory.tags);
      const vectors = await embed([text]);
      if (vectors[0]) {
        this.store.upsertEmbedding(memory.id, vectors[0]);
      }
    } catch {
      // Embedding failure is non-fatal — search falls back to FTS/LIKE
    }

    return memory;
  }

  async search(input: SearchInput): Promise<MemoryRecord[]> {
    const project = this.store.getOrCreateProject(input.projectRoot);
    const limit = clamp(input.k ?? 8, 1, 25);
    const fetchLimit = input.tags?.length ? limit * 4 : limit * 2;

    let queryVector: Float32Array | undefined;
    try {
      const vectors = await embed([input.query]);
      if (vectors[0]) {
        queryVector = new Float32Array(vectors[0]);
      }
    } catch {
      // Fall back to text search if embedding fails
    }

    let results = this.store.searchMemories(
      project.id,
      input.query,
      fetchLimit,
      input.includeArchived ?? false,
      input.kinds?.length ? input.kinds : undefined,
      queryVector
    );

    if (input.tags?.length) {
      const requiredTags = normalizeTags(input.tags);
      results = results.filter((memory) => requiredTags.every((tag) => memory.tags.includes(tag)));
    }

    return results.slice(0, limit);
  }

  get(projectRoot: string, id: number): MemoryRecord {
    const project = this.store.getOrCreateProject(projectRoot);
    const memory = this.store.getMemory(id);
    if (!memory || memory.projectId !== project.id) {
      throw new Error(`Memory not found for project: ${id}`);
    }

    return memory;
  }

  projectBrief(projectRoot: string): Record<string, MemoryRecord[]> {
    const project = this.store.getOrCreateProject(projectRoot);
    return this.store.projectBrief(project.id);
  }

  async update(input: {
    projectRoot: string;
    id: number;
    content?: string;
    summary?: string;
    whyUsefulLater?: string;
    tags?: string[];
    confidence?: Confidence;
    archive?: boolean;
    reason?: string;
  }): Promise<MemoryRecord> {
    const project = this.store.getOrCreateProject(input.projectRoot);
    const memory = this.store.getMemory(input.id);
    if (!memory || memory.projectId !== project.id) {
      throw new Error(`Memory not found for project: ${input.id}`);
    }

    if (input.content && looksLikeSecret(input.content)) {
      throw new MemoryQualityError(["Updated memory content looks like it may contain a secret or credential."]);
    }

    if (input.whyUsefulLater && looksLikeSecret(input.whyUsefulLater)) {
      throw new MemoryQualityError(["Updated usefulness rationale looks like it may contain a secret or credential."]);
    }

    const updated = this.store.updateMemory(
      input.id,
      {
        content: input.content?.trim(),
        summary: cleanOptional(input.summary),
        whyUsefulLater: input.whyUsefulLater?.trim(),
        tags: input.tags ? normalizeTags(input.tags) : undefined,
        confidence: input.confidence,
        archivedAt: input.archive ? new Date().toISOString() : undefined
      },
      input.reason ?? "Memory updated."
    );

    if (!updated.archivedAt) {
      try {
        const text = memoryEmbedText(updated.content, updated.summary, updated.tags);
        const vectors = await embed([text]);
        if (vectors[0]) {
          this.store.upsertEmbedding(updated.id, vectors[0]);
        }
      } catch {
        // Non-fatal
      }
    }

    return updated;
  }

  forget(input: { projectRoot: string; id: number; hardDelete?: boolean; reason?: string }): {
    archived: boolean;
    deleted: boolean;
  } {
    const project = this.store.getOrCreateProject(input.projectRoot);
    const memory = this.store.getMemory(input.id);
    if (!memory || memory.projectId !== project.id) {
      throw new Error(`Memory not found for project: ${input.id}`);
    }

    const reason = input.reason ?? "Memory forgotten by request.";
    if (input.hardDelete) {
      this.store.hardDeleteMemory(input.id, reason);
      return { archived: false, deleted: true };
    }

    this.store.archiveMemory(input.id, reason);
    return { archived: true, deleted: false };
  }

  async captureTaskSummary(input: {
    projectRoot: string;
    taskSummary: string;
    durableLearnings: string[];
    testsRun: string[];
    shouldRemember: boolean;
  }): Promise<{ stored: MemoryRecord[]; skipped: string[] }> {
    if (!input.shouldRemember) {
      return { stored: [], skipped: ["shouldRemember was false."] };
    }

    const stored: MemoryRecord[] = [];
    const skipped: string[] = [];

    for (const learning of input.durableLearnings) {
      try {
        stored.push(
          await this.remember({
            projectRoot: input.projectRoot,
            kind: "handoff",
            content: learning,
            summary: input.taskSummary,
            whyUsefulLater:
              "Future agents can use this durable learning when working on related tasks in this project.",
            tags: ["task-summary"],
            confidence: "medium",
            source: "agent",
            sourceRef: input.testsRun.length ? `Tests run: ${input.testsRun.join(", ")}` : "No tests recorded"
          })
        );
      } catch (error) {
        skipped.push(error instanceof Error ? error.message : String(error));
      }
    }

    return { stored, skipped };
  }

  async backfillEmbeddings(): Promise<void> {
    const unembedded = this.store.getUnembeddedMemoryIds();
    if (unembedded.length === 0) {
      return;
    }

    const texts = unembedded.map((item) => item.text);
    try {
      const vectors = await embed(texts);
      for (let i = 0; i < unembedded.length; i++) {
        const vec = vectors[i];
        const item = unembedded[i];
        if (vec && item) {
          this.store.upsertEmbedding(item.memoryId, vec);
        }
      }
    } catch {
      // Non-fatal
    }
  }

  exportProject(projectRoot: string, includeArchived = false): ProjectExport {
    const project = this.store.getOrCreateProject(projectRoot);
    return {
      exportedAt: new Date().toISOString(),
      project,
      memories: this.store.listMemories(project.id, includeArchived),
      events: this.store.listEvents(project.id)
    };
  }

  async importProject(projectRoot: string, exportJson: unknown): Promise<{ imported: number; skipped: number }> {
    const projectExport = validateProjectExport(exportJson);
    let imported = 0;
    let skipped = 0;

    for (const memory of projectExport.memories) {
      try {
        await this.remember({
          projectRoot,
          kind: memory.kind,
          content: memory.content,
          summary: memory.summary ?? undefined,
          whyUsefulLater: memory.whyUsefulLater,
          tags: memory.tags,
          confidence: memory.confidence,
          source: memory.source ?? "import",
          sourceRef: memory.sourceRef ?? `Imported from ${projectExport.project.rootPath}`
        });
        imported += 1;
      } catch {
        skipped += 1;
      }
    }

    return { imported, skipped };
  }

  linkProjectPaths(
    primaryProjectRoot: string,
    additionalProjectRoot: string
  ): { projectRoot: string; knownPaths: string[]; warning?: string } {
    const primary = this.store.getOrCreateProject(primaryProjectRoot);
    const additionalRoot = normalizeProjectRoot(additionalProjectRoot);
    const additionalRemote = getGitRemote(additionalRoot);
    const additionalFingerprint = fingerprintRemote(additionalRemote);

    if (primary.remoteFingerprint && additionalFingerprint && primary.remoteFingerprint !== additionalFingerprint) {
      return {
        projectRoot: primary.rootPath,
        knownPaths: primary.knownPaths,
        warning: "The two paths have different git remotes. No paths were linked."
      };
    }

    const project = this.store.linkProjectPaths(primary.rootPath, additionalRoot);
    return {
      projectRoot: project.rootPath,
      knownPaths: project.knownPaths
    };
  }

  possibleProjectMatches(projectRoot: string): { currentRoot: string; matches: string[] } {
    const root = normalizeProjectRoot(projectRoot);
    const remote = getGitRemote(root);
    const remoteFingerprint = fingerprintRemote(remote);
    if (!remoteFingerprint) {
      return { currentRoot: root, matches: [] };
    }

    const matches = this.store
      .findProjectsByRemoteFingerprint(remoteFingerprint)
      .flatMap((project) => project.knownPaths)
      .filter((knownPath) => knownPath !== root);

    return { currentRoot: root, matches: Array.from(new Set(matches)).sort() };
  }
}

export class UserMemoryService {
  constructor(private readonly store: ProjectMemoryStore) {}

  async remember(input: UserRememberInput): Promise<UserMemoryRecord> {
    const existing = this.store.listActiveUserMemories();
    const quality = evaluateUserMemoryQuality(input, existing);
    if (!quality.ok) {
      throw new MemoryQualityError(quality.reasons);
    }

    const tags = normalizeTags(input.tags);
    const memory = this.store.createUserMemory({
      kind: input.kind,
      content: input.content.trim(),
      summary: cleanOptional(input.summary),
      whyUsefulLater: input.whyUsefulLater.trim(),
      tags,
      confidence: input.confidence ?? "medium",
      source: cleanOptional(input.source),
      sourceRef: cleanOptional(input.sourceRef)
    });

    try {
      const text = memoryEmbedText(memory.content, memory.summary, memory.tags);
      const vectors = await embed([text]);
      if (vectors[0]) {
        this.store.upsertUserEmbedding(memory.id, vectors[0]);
      }
    } catch {
      // Non-fatal
    }

    return memory;
  }

  async search(input: UserSearchInput): Promise<UserMemoryRecord[]> {
    const limit = clamp(input.k ?? 8, 1, 25);
    const fetchLimit = input.tags?.length ? limit * 4 : limit * 2;

    let queryVector: Float32Array | undefined;
    try {
      const vectors = await embed([input.query]);
      if (vectors[0]) {
        queryVector = new Float32Array(vectors[0]);
      }
    } catch {
      // Fall back to text search
    }

    let results = this.store.searchUserMemories(
      input.query,
      fetchLimit,
      input.includeArchived ?? false,
      input.kinds?.length ? input.kinds : undefined,
      queryVector
    );

    if (input.tags?.length) {
      const requiredTags = normalizeTags(input.tags);
      results = results.filter((memory) => requiredTags.every((tag) => memory.tags.includes(tag)));
    }

    return results.slice(0, limit);
  }

  get(id: number): UserMemoryRecord {
    const memory = this.store.getUserMemory(id);
    if (!memory) {
      throw new Error(`User memory not found: ${id}`);
    }
    return memory;
  }

  brief(): Record<string, UserMemoryRecord[]> {
    return this.store.userMemoryBrief();
  }

  async update(input: {
    id: number;
    content?: string;
    summary?: string;
    whyUsefulLater?: string;
    tags?: string[];
    confidence?: Confidence;
    archive?: boolean;
    reason?: string;
  }): Promise<UserMemoryRecord> {
    const memory = this.store.getUserMemory(input.id);
    if (!memory) {
      throw new Error(`User memory not found: ${input.id}`);
    }

    if (input.content && looksLikeSecret(input.content)) {
      throw new MemoryQualityError(["Updated memory content looks like it may contain a secret or credential."]);
    }

    if (input.whyUsefulLater && looksLikeSecret(input.whyUsefulLater)) {
      throw new MemoryQualityError(["Updated usefulness rationale looks like it may contain a secret or credential."]);
    }

    const updated = this.store.updateUserMemory(
      input.id,
      {
        content: input.content?.trim(),
        summary: cleanOptional(input.summary),
        whyUsefulLater: input.whyUsefulLater?.trim(),
        tags: input.tags ? normalizeTags(input.tags) : undefined,
        confidence: input.confidence,
        archivedAt: input.archive ? new Date().toISOString() : undefined
      },
      input.reason ?? "User memory updated."
    );

    if (!updated.archivedAt) {
      try {
        const text = memoryEmbedText(updated.content, updated.summary, updated.tags);
        const vectors = await embed([text]);
        if (vectors[0]) {
          this.store.upsertUserEmbedding(updated.id, vectors[0]);
        }
      } catch {
        // Non-fatal
      }
    }

    return updated;
  }

  forget(input: { id: number; hardDelete?: boolean; reason?: string }): { archived: boolean; deleted: boolean } {
    const memory = this.store.getUserMemory(input.id);
    if (!memory) {
      throw new Error(`User memory not found: ${input.id}`);
    }

    const reason = input.reason ?? "User memory forgotten by request.";
    if (input.hardDelete) {
      this.store.hardDeleteUserMemory(input.id, reason);
      return { archived: false, deleted: true };
    }

    this.store.archiveUserMemory(input.id, reason);
    return { archived: true, deleted: false };
  }

  async backfillEmbeddings(): Promise<void> {
    const unembedded = this.store.getUnembeddedUserMemoryIds();
    if (unembedded.length === 0) {
      return;
    }

    const texts = unembedded.map((item) => item.text);
    try {
      const vectors = await embed(texts);
      for (let i = 0; i < unembedded.length; i++) {
        const vec = vectors[i];
        const item = unembedded[i];
        if (vec && item) {
          this.store.upsertUserEmbedding(item.memoryId, vec);
        }
      }
    } catch {
      // Non-fatal
    }
  }

  export(includeArchived = false): UserMemoryExport {
    return {
      exportedAt: new Date().toISOString(),
      memories: this.store.listUserMemories(includeArchived),
      events: this.store.listUserEvents()
    };
  }

  async import(exportJson: unknown): Promise<{ imported: number; skipped: number }> {
    const userExport = validateUserMemoryExport(exportJson);
    let imported = 0;
    let skipped = 0;

    for (const memory of userExport.memories) {
      try {
        await this.remember({
          kind: memory.kind,
          content: memory.content,
          summary: memory.summary ?? undefined,
          whyUsefulLater: memory.whyUsefulLater,
          tags: memory.tags,
          confidence: memory.confidence,
          source: memory.source ?? "import",
          sourceRef: memory.sourceRef ?? "Imported user memory"
        });
        imported += 1;
      } catch {
        skipped += 1;
      }
    }

    return { imported, skipped };
  }
}

function normalizeTags(tags: string[] | undefined): string[] {
  return Array.from(
    new Set(
      (tags ?? [])
        .map((tag) => tag.trim().toLowerCase())
        .filter((tag) => tag.length > 0 && /^[a-z0-9][a-z0-9_-]*$/.test(tag))
    )
  ).sort();
}

function cleanOptional(value: string | null | undefined): string | null {
  const cleaned = value?.trim();
  return cleaned ? cleaned : null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.floor(value)));
}

function validateProjectExport(value: unknown): ProjectExport {
  if (!value || typeof value !== "object") {
    throw new Error("Export must be an object.");
  }

  const candidate = value as Record<string, unknown>;
  if (!candidate.project || typeof candidate.project !== "object") {
    throw new Error("Invalid project memory export shape.");
  }

  if (!Array.isArray(candidate.memories) || !Array.isArray(candidate.events)) {
    throw new Error("Invalid project memory export shape.");
  }

  const validKinds = new Set<string>(memoryKinds);
  for (const memory of candidate.memories) {
    if (!memory || typeof memory !== "object") {
      throw new Error("Invalid memory record in export.");
    }
    const m = memory as Record<string, unknown>;
    if (typeof m.content !== "string" || !m.content.trim()) {
      throw new Error("Memory record missing required content field.");
    }
    if (typeof m.kind !== "string" || !validKinds.has(m.kind)) {
      throw new Error(`Memory record has invalid kind: ${String(m.kind)}.`);
    }
    if (typeof m.whyUsefulLater !== "string" || !m.whyUsefulLater.trim()) {
      throw new Error("Memory record missing required whyUsefulLater field.");
    }
  }

  return candidate as unknown as ProjectExport;
}

function validateUserMemoryExport(value: unknown): UserMemoryExport {
  if (!value || typeof value !== "object") {
    throw new Error("Export must be an object.");
  }

  const candidate = value as Record<string, unknown>;
  if (!Array.isArray(candidate.memories) || !Array.isArray(candidate.events)) {
    throw new Error("Invalid user memory export shape.");
  }

  const validKinds = new Set<string>(userMemoryKinds);
  for (const memory of candidate.memories) {
    if (!memory || typeof memory !== "object") {
      throw new Error("Invalid memory record in export.");
    }
    const m = memory as Record<string, unknown>;
    if (typeof m.content !== "string" || !m.content.trim()) {
      throw new Error("Memory record missing required content field.");
    }
    if (typeof m.kind !== "string" || !validKinds.has(m.kind)) {
      throw new Error(`Memory record has invalid kind: ${String(m.kind)}.`);
    }
    if (typeof m.whyUsefulLater !== "string" || !m.whyUsefulLater.trim()) {
      throw new Error("Memory record missing required whyUsefulLater field.");
    }
  }

  return candidate as unknown as UserMemoryExport;
}
