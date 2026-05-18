import type { MemoryRecord, QualityResult, RememberInput, UserMemoryRecord, UserRememberInput } from "./types.js";

const vaguePhrases = [
  "fixed the issue",
  "made changes",
  "updated the code",
  "worked on this",
  "did the task",
  "all done",
  "implemented it"
];

const commandOutputSignals = [
  /^npm (run|install|test|ci)\b/im,
  /^git (status|diff|log|show)\b/im,
  /^error: /im,
  /^warning: /im,
  /^passed\b/im,
  /^failed\b/im,
  /chunk id:/i,
  /process exited with code/i
];

const secretSignals = [
  /-----BEGIN (?:RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----/i,
  /\bAKIA[0-9A-Z]{16}\b/,
  /\b(?:sk|pk|rk|ghp|github_pat|xoxb|xoxp|xoxa|glpat|hf)_[A-Za-z0-9_-]{20,}\b/,
  /\bsk-[A-Za-z0-9_-]{20,}\b/,
  /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/,
  /^\s*[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PRIVATE_KEY)\s*=\s*.+$/im,
  /\b[A-Za-z0-9+/]{48,}={0,2}\b/
];

export function evaluateMemoryQuality(
  input: RememberInput,
  existing: Array<Pick<MemoryRecord, "content">> = []
): QualityResult {
  const reasons: string[] = [];
  const content = input.content.trim();
  const whyUsefulLater = input.whyUsefulLater?.trim() ?? "";

  if (content.length < 40 || wordCount(content) < 7) {
    reasons.push("Memory content is too short to be durable.");
  }

  if (!whyUsefulLater || whyUsefulLater.length < 20 || wordCount(whyUsefulLater) < 4) {
    reasons.push("Memory must explain why it will be useful later.");
  }

  if (vaguePhrases.some((phrase) => content.toLowerCase().includes(phrase))) {
    reasons.push("Memory content is too vague.");
  }

  if (commandOutputSignals.some((signal) => signal.test(content))) {
    reasons.push("Memory looks like routine command output or task status.");
  }

  if (looksLikeSecret(content) || looksLikeSecret(whyUsefulLater)) {
    reasons.push("Memory looks like it may contain a secret or credential.");
  }

  if (isDuplicate(content, existing)) {
    reasons.push("Memory duplicates an existing active memory.");
  }

  return {
    ok: reasons.length === 0,
    reasons
  };
}

export function looksLikeSecret(value: string): boolean {
  if (secretSignals.some((signal) => signal.test(value))) {
    return true;
  }

  return value
    .split(/\s+/)
    .some(
      (part) => part.length >= 40 && /[a-z]/.test(part) && /[A-Z]/.test(part) && /\d/.test(part) && /[-_+/=]/.test(part)
    );
}

function isDuplicate(content: string, existing: Array<{ content: string }>): boolean {
  const normalized = normalizeForComparison(content);
  return existing.some((memory) => normalizeForComparison(memory.content) === normalized);
}

function normalizeForComparison(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function wordCount(value: string): number {
  return value.trim().split(/\s+/).filter(Boolean).length;
}

export function evaluateUserMemoryQuality(
  input: UserRememberInput,
  existing: Array<Pick<UserMemoryRecord, "content">> = []
): QualityResult {
  const reasons: string[] = [];
  const content = input.content.trim();
  const whyUsefulLater = input.whyUsefulLater?.trim() ?? "";

  if (content.length < 40 || wordCount(content) < 7) {
    reasons.push("Memory content is too short to be durable.");
  }

  if (!whyUsefulLater || whyUsefulLater.length < 20 || wordCount(whyUsefulLater) < 4) {
    reasons.push("Memory must explain why it will be useful later.");
  }

  if (vaguePhrases.some((phrase) => content.toLowerCase().includes(phrase))) {
    reasons.push("Memory content is too vague.");
  }

  if (commandOutputSignals.some((signal) => signal.test(content))) {
    reasons.push("Memory looks like routine command output or task status.");
  }

  if (looksLikeSecret(content) || looksLikeSecret(whyUsefulLater)) {
    reasons.push("Memory looks like it may contain a secret or credential.");
  }

  if (isDuplicate(content, existing)) {
    reasons.push("Memory duplicates an existing active user memory.");
  }

  return { ok: reasons.length === 0, reasons };
}
