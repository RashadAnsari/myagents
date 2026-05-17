import { Database } from "bun:sqlite";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fingerprintRemote, getGitRemote, normalizeProjectRoot, projectNameFromRoot } from "./paths.js";
import type { Confidence, MemoryEventRecord, MemoryKind, MemoryRecord, ProjectRecord } from "./types.js";

interface ProjectRow {
  id: number;
  root_path: string;
  name: string;
  git_remote: string | null;
  remote_fingerprint: string | null;
  known_paths_json: string;
  created_at: string;
  updated_at: string;
}

interface MemoryRow {
  id: number;
  project_id: number;
  kind: MemoryKind;
  content: string;
  summary: string | null;
  why_useful_later: string;
  tags_json: string;
  confidence: Confidence;
  source: string | null;
  source_ref: string | null;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
  use_count: number;
  archived_at: string | null;
}

interface EventRow {
  id: number;
  project_id: number;
  memory_id: number;
  action: string;
  reason: string | null;
  created_at: string;
}

export interface CreateMemoryParams {
  projectId: number;
  kind: MemoryKind;
  content: string;
  summary: string | null;
  whyUsefulLater: string;
  tags: string[];
  confidence: Confidence;
  source: string | null;
  sourceRef: string | null;
}

export class ProjectMemoryStore {
  private readonly db: Database;

  constructor(dbPath: string) {
    mkdirSync(path.dirname(dbPath), { recursive: true });
    this.db = new Database(dbPath);
    this.db.exec("PRAGMA journal_mode = WAL;");
    this.db.exec("PRAGMA foreign_keys = ON;");
    this.migrate();
  }

  close(): void {
    this.db.close();
  }

  getOrCreateProject(projectRoot: string): ProjectRecord {
    const rootPath = normalizeProjectRoot(projectRoot);
    const existing = this.db.query("SELECT * FROM projects WHERE root_path = ?").get(rootPath) as
      | ProjectRow
      | undefined;
    if (existing) {
      return mapProject(existing);
    }

    const gitRemote = getGitRemote(rootPath);
    const remoteFingerprint = fingerprintRemote(gitRemote);
    const now = new Date().toISOString();
    const result = this.db
      .query(
        `INSERT INTO projects (root_path, name, git_remote, remote_fingerprint, known_paths_json, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`
      )
      .run(rootPath, projectNameFromRoot(rootPath), gitRemote, remoteFingerprint, JSON.stringify([rootPath]), now, now);

    return this.getProjectById(Number(result.lastInsertRowid));
  }

  getProjectById(id: number): ProjectRecord {
    const row = this.db.query("SELECT * FROM projects WHERE id = ?").get(id) as ProjectRow | undefined;
    if (!row) {
      throw new Error(`Project not found: ${id}`);
    }

    return mapProject(row);
  }

  findProjectsByRemoteFingerprint(remoteFingerprint: string): ProjectRecord[] {
    const rows = this.db
      .query("SELECT * FROM projects WHERE remote_fingerprint = ? ORDER BY updated_at DESC")
      .all(remoteFingerprint) as ProjectRow[];
    return rows.map(mapProject);
  }

  listActiveMemories(projectId: number): MemoryRecord[] {
    const rows = this.db
      .query("SELECT * FROM memories WHERE project_id = ? AND archived_at IS NULL ORDER BY updated_at DESC")
      .all(projectId) as MemoryRow[];
    return rows.map(mapMemory);
  }

  listMemories(projectId: number, includeArchived = false): MemoryRecord[] {
    const where = includeArchived ? "project_id = ?" : "project_id = ? AND archived_at IS NULL";
    const rows = this.db
      .query(`SELECT * FROM memories WHERE ${where} ORDER BY updated_at DESC`)
      .all(projectId) as MemoryRow[];
    return rows.map(mapMemory);
  }

  getMemory(id: number): MemoryRecord | null {
    const row = this.db.query("SELECT * FROM memories WHERE id = ?").get(id) as MemoryRow | undefined;
    return row ? mapMemory(row) : null;
  }

  createMemory(params: CreateMemoryParams): MemoryRecord {
    const now = new Date().toISOString();
    const result = this.db
      .query(
        `INSERT INTO memories (
          project_id, kind, content, summary, why_useful_later, tags_json, confidence,
          source, source_ref, created_at, updated_at, use_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)`
      )
      .run(
        params.projectId,
        params.kind,
        params.content,
        params.summary,
        params.whyUsefulLater,
        JSON.stringify(params.tags),
        params.confidence,
        params.source,
        params.sourceRef,
        now,
        now
      );
    const memory = this.getMemory(Number(result.lastInsertRowid));
    if (!memory) {
      throw new Error("Failed to create memory.");
    }

    this.upsertFts(memory);
    this.addEvent(memory.id, "created", params.whyUsefulLater);
    return memory;
  }

  updateMemory(
    id: number,
    updates: Partial<
      Pick<MemoryRecord, "content" | "summary" | "whyUsefulLater" | "tags" | "confidence" | "archivedAt">
    >,
    reason: string
  ): MemoryRecord {
    const existing = this.getMemory(id);
    if (!existing) {
      throw new Error(`Memory not found: ${id}`);
    }

    const next = {
      content: updates.content ?? existing.content,
      summary: updates.summary ?? existing.summary,
      whyUsefulLater: updates.whyUsefulLater ?? existing.whyUsefulLater,
      tags: updates.tags ?? existing.tags,
      confidence: updates.confidence ?? existing.confidence,
      archivedAt: updates.archivedAt ?? existing.archivedAt,
      updatedAt: new Date().toISOString()
    };

    this.db
      .query(
        `UPDATE memories
         SET content = ?, summary = ?, why_useful_later = ?, tags_json = ?, confidence = ?, archived_at = ?, updated_at = ?
         WHERE id = ?`
      )
      .run(
        next.content,
        next.summary,
        next.whyUsefulLater,
        JSON.stringify(next.tags),
        next.confidence,
        next.archivedAt,
        next.updatedAt,
        id
      );

    const memory = this.getMemory(id);
    if (!memory) {
      throw new Error(`Memory not found after update: ${id}`);
    }

    this.upsertFts(memory);
    this.addEvent(memory.id, "updated", reason);
    return memory;
  }

  archiveMemory(id: number, reason: string): MemoryRecord {
    const existing = this.getMemory(id);
    if (!existing) {
      throw new Error(`Memory not found: ${id}`);
    }

    const archivedAt = new Date().toISOString();
    this.db.query("UPDATE memories SET archived_at = ?, updated_at = ? WHERE id = ?").run(archivedAt, archivedAt, id);

    const memory = this.getMemory(id);
    if (!memory) {
      throw new Error(`Memory not found after archive: ${id}`);
    }

    this.upsertFts(memory);
    this.addEvent(id, "forgotten", reason);
    return memory;
  }

  hardDeleteMemory(id: number, reason: string): void {
    const memory = this.getMemory(id);
    if (!memory) {
      throw new Error(`Memory not found: ${id}`);
    }

    this.db.query("DELETE FROM memory_fts WHERE memory_id = ?").run(id);
    this.db.query("DELETE FROM memories WHERE id = ?").run(id);
    this.addEvent(id, "hard_deleted", reason, memory.projectId);
  }

  searchMemories(
    projectId: number,
    query: string,
    limit: number,
    includeArchived = false,
    kinds?: MemoryKind[]
  ): MemoryRecord[] {
    const matchQuery = buildFtsQuery(query);
    if (!matchQuery) {
      return this.likeSearch(projectId, query, limit, includeArchived, kinds);
    }

    try {
      const archivedWhere = includeArchived ? "" : "AND memories.archived_at IS NULL";
      const kindsWhere = kinds?.length ? `AND memories.kind IN (${kinds.map(() => "?").join(", ")})` : "";
      const rows = this.db
        .query(
          `SELECT memories.*
           FROM memory_fts
           JOIN memories ON memories.id = memory_fts.memory_id
           WHERE memories.project_id = ?
             ${archivedWhere}
             ${kindsWhere}
             AND memory_fts MATCH ?
           ORDER BY bm25(memory_fts), memories.confidence DESC, memories.updated_at DESC
           LIMIT ?`
        )
        .all(projectId, ...(kinds ?? []), matchQuery, limit) as MemoryRow[];

      const memories = rows.map(mapMemory);
      if (memories.length === 0) {
        return this.likeSearch(projectId, query, limit, includeArchived, kinds);
      }

      this.markUsed(memories.map((memory) => memory.id));
      return memories;
    } catch {
      return this.likeSearch(projectId, query, limit, includeArchived, kinds);
    }
  }

  projectBrief(projectId: number): Record<string, MemoryRecord[]> {
    const active = this.listActiveMemories(projectId);
    const byKind = (kinds: MemoryKind[], limit: number) =>
      active
        .filter((memory) => kinds.includes(memory.kind))
        .sort(compareBriefPriority)
        .slice(0, limit);

    return {
      conventions: byKind(["convention", "preference"], 8),
      decisions: byKind(["decision", "architecture"], 8),
      pitfalls: byKind(["gotcha", "bug"], 8),
      recent: active.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).slice(0, 8)
    };
  }

  listEvents(projectId: number): MemoryEventRecord[] {
    const rows = this.db
      .query(
        `SELECT memory_events.*
         FROM memory_events
         WHERE memory_events.project_id = ?
         ORDER BY memory_events.created_at ASC`
      )
      .all(projectId) as EventRow[];
    return rows.map(mapEvent);
  }

  addEvent(memoryId: number, action: string, reason: string | null, projectId?: number): void {
    const resolvedProjectId = projectId ?? this.getMemory(memoryId)?.projectId;
    if (!resolvedProjectId) {
      throw new Error(`Cannot record memory event without project id: ${memoryId}`);
    }

    this.db
      .query("INSERT INTO memory_events (project_id, memory_id, action, reason, created_at) VALUES (?, ?, ?, ?, ?)")
      .run(resolvedProjectId, memoryId, action, reason, new Date().toISOString());
  }

  linkProjectPaths(primaryProjectRoot: string, additionalProjectRoot: string): ProjectRecord {
    const primary = this.getOrCreateProject(primaryProjectRoot);
    const additionalPath = normalizeProjectRoot(additionalProjectRoot);
    const knownPaths = Array.from(new Set([...primary.knownPaths, additionalPath])).sort();
    const now = new Date().toISOString();

    this.db
      .query("UPDATE projects SET known_paths_json = ?, updated_at = ? WHERE id = ?")
      .run(JSON.stringify(knownPaths), now, primary.id);

    return this.getProjectById(primary.id);
  }

  private likeSearch(
    projectId: number,
    query: string,
    limit: number,
    includeArchived: boolean,
    kinds?: MemoryKind[]
  ): MemoryRecord[] {
    const archivedWhere = includeArchived ? "" : "AND archived_at IS NULL";
    const kindsWhere = kinds?.length ? `AND kind IN (${kinds.map(() => "?").join(", ")})` : "";
    const pattern = `%${query.trim().replaceAll("%", "\\%").replaceAll("_", "\\_")}%`;
    const rows = this.db
      .query(
        `SELECT *
         FROM memories
         WHERE project_id = ?
           ${archivedWhere}
           ${kindsWhere}
           AND (content LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\' OR why_useful_later LIKE ? ESCAPE '\\')
         ORDER BY confidence DESC, updated_at DESC
         LIMIT ?`
      )
      .all(projectId, ...(kinds ?? []), pattern, pattern, pattern, limit) as MemoryRow[];

    const memories = rows.map(mapMemory);
    this.markUsed(memories.map((memory) => memory.id));
    return memories;
  }

  private markUsed(ids: number[]): void {
    if (ids.length === 0) {
      return;
    }

    const now = new Date().toISOString();
    const update = this.db.query("UPDATE memories SET last_used_at = ?, use_count = use_count + 1 WHERE id = ?");
    const transaction = this.db.transaction((memoryIds: number[]) => {
      for (const id of memoryIds) {
        update.run(now, id);
      }
    });
    transaction(ids);
  }

  private upsertFts(memory: MemoryRecord): void {
    this.db.query("DELETE FROM memory_fts WHERE memory_id = ?").run(memory.id);
    if (memory.archivedAt) {
      return;
    }

    this.db
      .query("INSERT INTO memory_fts (memory_id, content, summary, tags, why_useful_later) VALUES (?, ?, ?, ?, ?)")
      .run(memory.id, memory.content, memory.summary ?? "", memory.tags.join(" "), memory.whyUsefulLater);
  }

  private migrate(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        root_path TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        git_remote TEXT,
        remote_fingerprint TEXT,
        known_paths_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_projects_remote_fingerprint ON projects(remote_fingerprint);

      CREATE TABLE IF NOT EXISTS memories (
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

      CREATE INDEX IF NOT EXISTS idx_memories_project_active ON memories(project_id, archived_at);
      CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);

      CREATE TABLE IF NOT EXISTS memory_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        memory_id INTEGER,
        action TEXT NOT NULL,
        reason TEXT,
        created_at TEXT NOT NULL
      );

      CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
        memory_id UNINDEXED,
        content,
        summary,
        tags,
        why_useful_later
      );
    `);

    this.ensureColumn("memory_events", "project_id", "INTEGER");
    this.db.exec(`
      UPDATE memory_events
      SET project_id = (
        SELECT memories.project_id
        FROM memories
        WHERE memories.id = memory_events.memory_id
      )
      WHERE project_id IS NULL
        AND EXISTS (
          SELECT 1
          FROM memories
          WHERE memories.id = memory_events.memory_id
        );
    `);
  }

  private ensureColumn(tableName: string, columnName: string, columnDefinition: string): void {
    if (!/^[a-z_][a-z0-9_]*$/i.test(tableName) || !/^[a-z_][a-z0-9_]*$/i.test(columnName)) {
      throw new Error(`Invalid identifier: ${tableName}.${columnName}`);
    }
    const columns = this.db.query(`PRAGMA table_info(${tableName})`).all() as Array<{ name: string }>;
    if (!columns.some((column) => column.name === columnName)) {
      this.db.exec(`ALTER TABLE ${tableName} ADD COLUMN ${columnName} ${columnDefinition}`);
    }
  }
}

function mapProject(row: ProjectRow): ProjectRecord {
  return {
    id: row.id,
    rootPath: row.root_path,
    name: row.name,
    gitRemote: row.git_remote,
    remoteFingerprint: row.remote_fingerprint,
    knownPaths: parseJsonArray(row.known_paths_json),
    createdAt: row.created_at,
    updatedAt: row.updated_at
  };
}

function mapMemory(row: MemoryRow): MemoryRecord {
  return {
    id: row.id,
    projectId: row.project_id,
    kind: row.kind,
    content: row.content,
    summary: row.summary,
    whyUsefulLater: row.why_useful_later,
    tags: parseJsonArray(row.tags_json),
    confidence: row.confidence,
    source: row.source,
    sourceRef: row.source_ref,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    lastUsedAt: row.last_used_at,
    useCount: row.use_count,
    archivedAt: row.archived_at
  };
}

function mapEvent(row: EventRow): MemoryEventRecord {
  return {
    id: row.id,
    projectId: row.project_id,
    memoryId: row.memory_id,
    action: row.action,
    reason: row.reason,
    createdAt: row.created_at
  };
}

function parseJsonArray(value: string): string[] {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function buildFtsQuery(query: string): string | null {
  const terms = Array.from(new Set(query.toLowerCase().match(/[a-z0-9_]{2,}/g) ?? []));
  if (terms.length === 0) {
    return null;
  }

  return terms.map((term) => `${term}*`).join(" OR ");
}

function compareBriefPriority(a: MemoryRecord, b: MemoryRecord): number {
  const confidenceScore = (value: Confidence) => (value === "high" ? 3 : value === "medium" ? 2 : 1);
  const confidenceDelta = confidenceScore(b.confidence) - confidenceScore(a.confidence);
  if (confidenceDelta !== 0) {
    return confidenceDelta;
  }

  const usageDelta = b.useCount - a.useCount;
  if (usageDelta !== 0) {
    return usageDelta;
  }

  return b.updatedAt.localeCompare(a.updatedAt);
}
