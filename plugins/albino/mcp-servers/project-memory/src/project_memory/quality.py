import re
import sys

# Detect-secrets plugins initialized once at module level.
# Pattern-based plugins only: no entropy detectors, which produce false positives on natural language.
try:
    from detect_secrets.plugins.artifactory import ArtifactoryDetector
    from detect_secrets.plugins.aws import AWSKeyDetector
    from detect_secrets.plugins.azure_storage_key import AzureStorageKeyDetector
    from detect_secrets.plugins.basic_auth import BasicAuthDetector
    from detect_secrets.plugins.cloudant import CloudantDetector
    from detect_secrets.plugins.discord import DiscordBotTokenDetector
    from detect_secrets.plugins.github_token import GitHubTokenDetector
    from detect_secrets.plugins.gitlab_token import GitLabTokenDetector
    from detect_secrets.plugins.ibm_cloud_iam import IbmCloudIamDetector
    from detect_secrets.plugins.ibm_cos_hmac import IbmCosHmacDetector
    from detect_secrets.plugins.jwt import JwtTokenDetector
    from detect_secrets.plugins.mailchimp import MailchimpDetector
    from detect_secrets.plugins.npm import NpmDetector
    from detect_secrets.plugins.openai import OpenAIDetector
    from detect_secrets.plugins.private_key import PrivateKeyDetector
    from detect_secrets.plugins.pypi_token import PypiTokenDetector
    from detect_secrets.plugins.sendgrid import SendGridDetector
    from detect_secrets.plugins.slack import SlackDetector
    from detect_secrets.plugins.softlayer import SoftlayerDetector
    from detect_secrets.plugins.square_oauth import SquareOAuthDetector
    from detect_secrets.plugins.stripe import StripeDetector
    from detect_secrets.plugins.telegram_token import TelegramBotTokenDetector
    from detect_secrets.plugins.twilio import TwilioKeyDetector

    _DS_PLUGINS = [
        ArtifactoryDetector(),
        AWSKeyDetector(),
        AzureStorageKeyDetector(),
        BasicAuthDetector(),
        CloudantDetector(),
        DiscordBotTokenDetector(),
        GitHubTokenDetector(),
        GitLabTokenDetector(),
        IbmCloudIamDetector(),
        IbmCosHmacDetector(),
        JwtTokenDetector(),
        MailchimpDetector(),
        NpmDetector(),
        OpenAIDetector(),
        PrivateKeyDetector(),
        PypiTokenDetector(),
        SendGridDetector(),
        SlackDetector(),
        SoftlayerDetector(),
        SquareOAuthDetector(),
        StripeDetector(),
        TelegramBotTokenDetector(),
        TwilioKeyDetector(),
    ]
except ImportError:  # pragma: no cover
    _DS_PLUGINS = []
    print("project-memory: detect-secrets unavailable, using regex-only secret detection", file=sys.stderr)

# Targeted regexes covering gaps not handled by detect-secrets pattern plugins:
# - Stripe test keys (StripeDetector only covers _live_ with exactly 24 chars)
# - GitHub PAT variable length (GitHubTokenDetector requires exactly 36 chars)
# - Generic sdk prefixes: sk_, pk_, rk_, hf_, github_pat_
# - GitLab old underscore format (GitLabTokenDetector uses hyphen)
# - Generic sk- hyphen-prefixed tokens (OpenAIDetector only covers old T3BlbkFJ marker)
# - Plaintext keyword=value assignments (KeywordDetector requires source-code context)
# - Long base64 blobs not covered by structural patterns above
_SECRET_SIGNALS = [
    re.compile(r"\b(?:sk|pk|rk|hf|github_pat)_[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bglpat_[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"^\s*[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|PRIVATE_KEY|AUTH_KEY|ACCESS_KEY)\s*=\s*\S+",
        re.MULTILINE | re.IGNORECASE,
    ),
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9+/]*[+/][A-Za-z0-9+/]{30,}={0,2}(?![A-Za-z0-9+/=])"),
]

_DUPLICATE_PROJECT_MSG = "Memory duplicates an existing active memory."
_DUPLICATE_USER_MSG = "Memory duplicates an existing active user memory."

_MIN_CONTENT_CHARS = 40
_MIN_CONTENT_WORDS = 7
_MIN_WHY_CHARS = 20
_MIN_WHY_WORDS = 4

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


def _detect_secrets_hit(value: str) -> bool:
    if not _DS_PLUGINS:
        return False
    for line in value.splitlines() or [value]:
        for plugin in _DS_PLUGINS:
            if plugin.analyze_line("_", line):
                return True
    return False


def looks_like_secret(value: str) -> bool:
    if _detect_secrets_hit(value):
        return True
    if any(sig.search(value) for sig in _SECRET_SIGNALS):
        return True
    # High-entropy mixed token heuristic: 40+ chars with lowercase, uppercase, digits, and symbols
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
    normalized_existing = {_normalize_for_comparison(c) for c in existing_contents}
    return normalized in normalized_existing


def evaluate_memory_quality(
    content: str,
    why_useful_later: str,
    existing_contents: list[str],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    content = content.strip()
    why = (why_useful_later or "").strip()

    if len(content) < _MIN_CONTENT_CHARS or _word_count(content) < _MIN_CONTENT_WORDS:
        reasons.append("Memory content is too short to be durable.")

    if not why or len(why) < _MIN_WHY_CHARS or _word_count(why) < _MIN_WHY_WORDS:
        reasons.append("Memory must explain why it will be useful later.")

    if any(phrase in content.lower() for phrase in _VAGUE_PHRASES):
        reasons.append("Memory content is too vague.")

    if any(sig.search(content) for sig in _COMMAND_OUTPUT_SIGNALS):
        reasons.append("Memory looks like routine command output or task status.")

    if looks_like_secret(content) or looks_like_secret(why):
        reasons.append("Memory looks like it may contain a secret or credential.")

    if _is_duplicate(content, existing_contents):
        reasons.append(_DUPLICATE_PROJECT_MSG)

    return len(reasons) == 0, reasons


def evaluate_user_memory_quality(
    content: str,
    why_useful_later: str,
    existing_contents: list[str],
) -> tuple[bool, list[str]]:
    ok, reasons = evaluate_memory_quality(content, why_useful_later, existing_contents)
    reasons = [_DUPLICATE_USER_MSG if r == _DUPLICATE_PROJECT_MSG else r for r in reasons]
    return ok, reasons
