export const memoryKinds = [
  "decision",
  "convention",
  "architecture",
  "workflow",
  "preference",
  "gotcha",
  "bug",
  "dependency",
  "testing",
  "handoff"
] as const;

export type MemoryKind = (typeof memoryKinds)[number];

export const confidenceValues = ["low", "medium", "high"] as const;

export type Confidence = (typeof confidenceValues)[number];

export interface ProjectRecord {
  id: number;
  rootPath: string;
  name: string;
  gitRemote: string | null;
  remoteFingerprint: string | null;
  knownPaths: string[];
  createdAt: string;
  updatedAt: string;
}

export interface MemoryRecord {
  id: number;
  projectId: number;
  kind: MemoryKind;
  content: string;
  summary: string | null;
  whyUsefulLater: string;
  tags: string[];
  confidence: Confidence;
  source: string | null;
  sourceRef: string | null;
  createdAt: string;
  updatedAt: string;
  lastUsedAt: string | null;
  useCount: number;
  archivedAt: string | null;
}

export interface RememberInput {
  projectRoot: string;
  kind: MemoryKind;
  content: string;
  summary?: string;
  whyUsefulLater?: string;
  tags?: string[];
  confidence?: Confidence;
  source?: string;
  sourceRef?: string;
}

export interface SearchInput {
  projectRoot: string;
  query: string;
  k?: number;
  kinds?: MemoryKind[];
  tags?: string[];
  includeArchived?: boolean;
}

export interface ProjectExport {
  exportedAt: string;
  project: ProjectRecord;
  memories: MemoryRecord[];
  events: MemoryEventRecord[];
}

export interface MemoryEventRecord {
  id: number;
  projectId: number;
  memoryId: number;
  action: string;
  reason: string | null;
  createdAt: string;
}

export interface QualityResult {
  ok: boolean;
  reasons: string[];
}

export const userMemoryKinds = [
  "preference",
  "behavior",
  "context",
  "workflow",
  "convention",
  "tool_preference",
  "communication"
] as const;

export type UserMemoryKind = (typeof userMemoryKinds)[number];

export interface UserMemoryRecord {
  id: number;
  kind: UserMemoryKind;
  content: string;
  summary: string | null;
  whyUsefulLater: string;
  tags: string[];
  confidence: Confidence;
  source: string | null;
  sourceRef: string | null;
  createdAt: string;
  updatedAt: string;
  lastUsedAt: string | null;
  useCount: number;
  archivedAt: string | null;
}

export interface UserRememberInput {
  kind: UserMemoryKind;
  content: string;
  summary?: string;
  whyUsefulLater: string;
  tags?: string[];
  confidence?: Confidence;
  source?: string;
  sourceRef?: string;
}

export interface UserSearchInput {
  query: string;
  k?: number;
  kinds?: UserMemoryKind[];
  tags?: string[];
  includeArchived?: boolean;
}

export interface UserMemoryEventRecord {
  id: number;
  memoryId: number | null;
  action: string;
  reason: string | null;
  createdAt: string;
}

export interface UserMemoryExport {
  exportedAt: string;
  memories: UserMemoryRecord[];
  events: UserMemoryEventRecord[];
}
