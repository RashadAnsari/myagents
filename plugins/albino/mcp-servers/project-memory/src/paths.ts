import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

export function defaultMemoryDir(): string {
  if (process.env.MYAGENTS_MEMORY_DIR) {
    return path.resolve(process.env.MYAGENTS_MEMORY_DIR);
  }

  return path.join(homedir(), ".myagents");
}

export function defaultDatabasePath(): string {
  if (process.env.MYAGENTS_MEMORY_DIR) {
    const dir = path.resolve(process.env.MYAGENTS_MEMORY_DIR);
    mkdirSync(dir, { recursive: true });
    return path.join(dir, "memory.sqlite");
  }

  const dir = path.join(homedir(), ".myagents", "project-memory");
  mkdirSync(dir, { recursive: true });
  return path.join(dir, "memory.sqlite");
}

export function normalizeProjectRoot(projectRoot: string): string {
  return path.resolve(projectRoot);
}

export function currentProjectRoot(): string {
  return normalizeProjectRoot(
    process.env.MYAGENTS_PROJECT_ROOT ?? process.env.INIT_CWD ?? process.env.PWD ?? process.cwd()
  );
}

export function projectNameFromRoot(rootPath: string): string {
  return path.basename(rootPath) || rootPath;
}

export function getGitRemote(rootPath: string): string | null {
  if (!existsSync(rootPath)) {
    return null;
  }

  try {
    const remote = execFileSync("git", ["-C", rootPath, "config", "--get", "remote.origin.url"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"]
    }).trim();
    return remote.length > 0 ? normalizeGitRemote(remote) : null;
  } catch {
    return null;
  }
}

export function normalizeGitRemote(remote: string): string {
  let normalized = remote.trim();
  normalized = normalized.replace(/^https?:\/\/([^/@]+@)?/i, "https://");
  normalized = normalized.replace(/^git@([^:]+):/, "https://$1/");
  normalized = normalized.replace(/\.git$/i, "");
  return normalized.toLowerCase();
}

export function fingerprintRemote(remote: string | null): string | null {
  if (!remote) {
    return null;
  }

  return createHash("sha256").update(remote).digest("hex");
}
