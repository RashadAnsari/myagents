import pytest

from agent_memory.quality import evaluate_memory_quality, evaluate_user_memory_quality, looks_like_secret

_GOOD_CONTENT = "Use postgres for all persistent storage to avoid adding Redis or Mongo to the stack unnecessarily."


class TestLooksLikeSecret:
    def test_pem_private_key(self):
        assert looks_like_secret("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAK\n-----END RSA PRIVATE KEY-----")

    def test_openssh_private_key(self):
        assert looks_like_secret("-----BEGIN OPENSSH PRIVATE KEY-----\nfoobar\n-----END OPENSSH PRIVATE KEY-----")

    def test_aws_access_key(self):
        assert looks_like_secret("AKIAIOSFODNN7EXAMPLE")

    def test_generic_token_prefix_sk(self):
        assert looks_like_secret("sk_live_abcdefghijklmnopqrstuvwxyz1234567890ab")

    def test_generic_token_prefix_ghp(self):
        assert looks_like_secret("ghp_abcdefghijklmnopqrstuvwxyzABCDEFGH")

    def test_generic_token_prefix_glpat(self):
        assert looks_like_secret("glpat_abcdefghijklmnopqrstuvwxyz1234")

    def test_jwt_token(self):
        assert looks_like_secret("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")

    def test_env_assignment_api_key(self):
        assert looks_like_secret("API_KEY=abc123verylongsecretvalue")

    def test_env_assignment_password(self):
        assert looks_like_secret("DATABASE_PASSWORD=supersecretpassword123")

    def test_base64_long_string(self):
        assert looks_like_secret("base64+ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwx")

    def test_stripe_live_key(self):
        assert looks_like_secret("sk_live_abcdefghijklmnopqrstuvwxyz1234567890ab")

    def test_stripe_test_key(self):
        assert looks_like_secret("sk_test_abcdefghijklmnopqrstuvwxyz12345678")

    def test_slack_token(self):
        assert looks_like_secret("xoxb-12345678901-12345678901-ABCDEFGHIJKLMNOPQRS")

    def test_twilio_account_sid(self):
        assert looks_like_secret("ACaaaabbbbccccdddd0000111122223333")

    def test_openai_project_key(self):
        assert looks_like_secret("sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd")

    def test_entropy_heuristic_mixed_case_digits_special(self):
        assert looks_like_secret("aAbBcC1234567890aAbBcC123456789/abcdefgh")

    def test_normal_content_not_secret(self):
        assert not looks_like_secret("Use postgres for all persistent storage needs.")

    def test_short_token_not_secret(self):
        assert not looks_like_secret("sk_short")

    def test_empty_string_not_secret(self):
        assert not looks_like_secret("")


class TestEvaluateMemoryQualityBoundaries:
    def test_passes_at_minimum_length(self):
        content = "Use postgres for the main data storage now"
        assert len(content.strip()) >= 40
        assert len([w for w in content.strip().split() if w]) >= 7
        ok, _ = evaluate_memory_quality(content, [])
        assert ok

    def test_rejects_content_too_short_chars(self):
        ok, reasons = evaluate_memory_quality("Too short.", [])
        assert not ok
        assert any("too short" in r.lower() for r in reasons)

    def test_rejects_content_too_few_words(self):
        ok, reasons = evaluate_memory_quality("a" * 40, [])
        assert not ok
        assert any("too short" in r.lower() for r in reasons)


class TestEvaluateMemoryQualityReasons:
    @pytest.mark.parametrize(
        "phrase",
        [
            "fixed the issue",
            "made changes",
            "updated the code",
            "worked on this",
            "did the task",
            "all done",
            "implemented it",
        ],
    )
    def test_rejects_vague_phrase(self, phrase):
        content = f"I {phrase} and everything is working correctly now in the system."
        ok, reasons = evaluate_memory_quality(content, [])
        assert not ok
        assert any("vague" in r.lower() for r in reasons)

    def test_rejects_command_output_npm(self):
        content = "npm run build\n> project@1.0.0 build\n> tsc --outDir dist\nThe build succeeded."
        ok, reasons = evaluate_memory_quality(content, [])
        assert not ok
        assert any("command output" in r.lower() for r in reasons)

    def test_rejects_command_output_git(self):
        content = "git status\nOn branch main\nnothing to commit, working tree clean\n"
        ok, reasons = evaluate_memory_quality(content, [])
        assert not ok

    def test_rejects_secret_in_content(self):
        content = "The API key is AKIAIOSFODNN7EXAMPLE and should be rotated regularly in production env."
        ok, reasons = evaluate_memory_quality(content, [])
        assert not ok
        assert any("secret" in r.lower() for r in reasons)

    def test_rejects_exact_duplicate(self):
        ok, reasons = evaluate_memory_quality(_GOOD_CONTENT, [_GOOD_CONTENT])
        assert not ok
        assert any("duplicates" in r.lower() for r in reasons)

    def test_rejects_normalized_duplicate(self):
        variant = _GOOD_CONTENT.upper().replace(".", "").replace(",", "")
        ok, reasons = evaluate_memory_quality(_GOOD_CONTENT, [variant])
        assert not ok
        assert any("duplicates" in r.lower() for r in reasons)

    def test_passes_non_duplicate(self):
        other = "Use Redis for caching session data to improve response times across all API endpoints."
        ok, _ = evaluate_memory_quality(_GOOD_CONTENT, [other])
        assert ok

    def test_multiple_reasons_accumulated(self):
        content = "I fixed the issue and everything is working correctly now in the system."
        ok, reasons = evaluate_memory_quality(content, [content])
        assert not ok
        assert len(reasons) >= 2  # vague + duplicate


class TestEvaluateUserMemoryQuality:
    def test_passes_valid_content(self):
        ok, _ = evaluate_user_memory_quality(_GOOD_CONTENT, [])
        assert ok

    def test_duplicate_message_uses_user_wording(self):
        ok, reasons = evaluate_user_memory_quality(_GOOD_CONTENT, [_GOOD_CONTENT])
        assert not ok
        assert any("user memory" in r.lower() for r in reasons)
        assert not any(r == "Memory duplicates an existing active memory." for r in reasons)

    def test_non_duplicate_reason_unchanged(self):
        ok, reasons = evaluate_user_memory_quality("short", [])
        assert not ok
        assert any("too short" in r.lower() for r in reasons)
