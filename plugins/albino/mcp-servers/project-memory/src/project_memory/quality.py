import re

_VAGUE_PHRASES = [
    "fixed the issue",
    "made changes",
    "updated the code",
    "worked on this",
    "did the task",
    "all done",
    "implemented it",
]

_COMMAND_OUTPUT_SIGNALS = [
    re.compile(r"^npm (run|install|test|ci)\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^git (status|diff|log|show)\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^error: ", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^warning: ", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^passed\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^failed\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"chunk id:", re.IGNORECASE),
    re.compile(r"process exited with code", re.IGNORECASE),
]

_SECRET_SIGNALS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|pk|rk|ghp|github_pat|xoxb|xoxp|xoxa|glpat|hf)_[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"^\s*[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PRIVATE_KEY)\s*=\s*.+$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9+/]*[+/][A-Za-z0-9+/]{40,}={0,2}\b"),
]


def looks_like_secret(value: str) -> bool:
    if any(sig.search(value) for sig in _SECRET_SIGNALS):
        return True
    return any(
        len(part) >= 40
        and any(c.islower() for c in part)
        and any(c.isupper() for c in part)
        and any(c.isdigit() for c in part)
        and any(c in "-_+/=" for c in part)
        for part in value.split()
    )


def _word_count(value: str) -> int:
    return len([w for w in value.strip().split() if w])


def _normalize_for_comparison(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _is_duplicate(content: str, existing_contents: list[str]) -> bool:
    normalized = _normalize_for_comparison(content)
    return any(_normalize_for_comparison(c) == normalized for c in existing_contents)


def evaluate_memory_quality(
    content: str,
    why_useful_later: str,
    existing_contents: list[str],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    content = content.strip()
    why = (why_useful_later or "").strip()

    if len(content) < 40 or _word_count(content) < 7:
        reasons.append("Memory content is too short to be durable.")

    if not why or len(why) < 20 or _word_count(why) < 4:
        reasons.append("Memory must explain why it will be useful later.")

    if any(phrase in content.lower() for phrase in _VAGUE_PHRASES):
        reasons.append("Memory content is too vague.")

    if any(sig.search(content) for sig in _COMMAND_OUTPUT_SIGNALS):
        reasons.append("Memory looks like routine command output or task status.")

    if looks_like_secret(content) or looks_like_secret(why):
        reasons.append("Memory looks like it may contain a secret or credential.")

    if _is_duplicate(content, existing_contents):
        reasons.append("Memory duplicates an existing active memory.")

    return len(reasons) == 0, reasons


def evaluate_user_memory_quality(
    content: str,
    why_useful_later: str,
    existing_contents: list[str],
) -> tuple[bool, list[str]]:
    ok, reasons = evaluate_memory_quality(content, why_useful_later, existing_contents)
    reasons = [
        r
        if r != "Memory duplicates an existing active memory."
        else "Memory duplicates an existing active user memory."
        for r in reasons
    ]
    return ok, reasons
