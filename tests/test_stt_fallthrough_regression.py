"""Regression tests for the STT auth-failure fall-through + config schema fix.

Covers:
1. _stt_auth_error detection (11 cases: real user 401, provider prose, SDK shapes, non-auth)
2. _transcribe_prepared_audio AUTO mode: openai 401 -> falls through chain -> success on elevenlabs
3. _transcribe_prepared_audio EXPLICIT mode: fails loudly with the provider's own error
4. _validate_config_key('stt.provider') is KNOWN (no false-alarm warning)
5. Real typos still flagged (stt.providerr, gateway.strictn)
"""
import sys

REPO = r"C:\Users\JUNA\AppData\Local\merlin\cache\scratch\merlin-fix-sprint"
sys.path.insert(0, REPO)

passed = failed = 0


def check(cond, label):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")


# ---------------------------------------------------------------- 1 + 2 + 3 STT
import tools.transcription_tools as tt

FAIL_401_OPENAI = {
    "success": False,
    "error": "openai STT error (HTTP 401): Incorrect API key provided: sk-ts-ES***SCAC",
}
FAIL_401_ELEVEN = {"success": False, "error": "ELEVENLABS_API_KEY not set"}
OK_ELEVEN = {"success": True, "transcript": "halo dunia", "provider": "elevenlabs"}

print("[1] auth-error detector")
DETECT_CASES = [
    (FAIL_401_OPENAI, True),                                  # real-world user case
    ({"success": False, "error": "GROQ_API_KEY not set"}, True),
    ({"success": False, "error": "Rate limit reached (HTTP 429)"}, False),
    ({"success": False, "error": "connection timeout after 60s"}, False),
    ({"success": False, "error": "audio file is not a valid WAV"}, False),
    ({"success": False, "error": "faster-whisper crashed"}, False),
    ({"success": True, "transcript": "hello"}, False),
    ("string garbage", False),
    (None, False),
    ({"success": False, "error": ""}, False),
]
for env, expect in DETECT_CASES:
    got = tt._stt_auth_error(env) is not None
    check(got == expect, f"detector: {str(env)[:58]} -> {expect}")

print("[2] AUTO mode falls through on 401")
tt._read_block_error = lambda p: None
tt._validate_audio_file = lambda *a, **k: None
tt.is_stt_enabled = lambda cfg: True
tt._prepare_audio_for_provider = lambda fp, prov, cfg, cleanup: fp
tt._load_stt_config = lambda: {}  # empty = AUTO (no explicit provider)
calls = []


def fake_dispatch(file_path, provider, stt_config, model=None, source=None):
    calls.append(provider)
    return OK_ELEVEN if provider == "elevenlabs" else FAIL_401_OPENAI


tt._dispatch_stt_provider = fake_dispatch
tt._get_provider = lambda cfg: "openai"  # auto-detect picked the invalid-key provider
tt._is_local_stt_provider = lambda p, c: False
tt.CLOUD_STT_PROVIDERS = frozenset()

result = tt._transcribe_prepared_audio("/fake/clip.wav")
check(result == OK_ELEVEN, "AUTO: user gets a real transcript despite the broken provider")
check(calls == ["openai", "mistral", "xai", "elevenlabs"],
      f"AUTO: chain order preserved ({calls})")

print("[3] EXPLICIT mode fails loudly")
calls.clear()
tt._load_stt_config = lambda: {"provider": "elevenlabs"}
tt._get_provider = lambda cfg: "elevenlabs"
tt._dispatch_stt_provider = lambda fp, p, cfg, model=None, source=None: (
    calls.append(p) or FAIL_401_ELEVEN)
result = tt._transcribe_prepared_audio("/fake/clip.wav")
check(result == FAIL_401_ELEVEN, "EXPLICIT: user's own error surfaces, no fallback")
check(calls == ["elevenlabs"], "EXPLICIT: no other provider is tried")

print("[4+5] config key schema")
from merlin_cli.config import _validate_config_key

ok, _ = _validate_config_key("stt.provider")
check(ok, "'stt.provider' recognized (no false-alarm warning)")
ok, _ = _validate_config_key("stt.providerr")
check(not ok, "typo 'stt.providerr' still flagged")
ok, _ = _validate_config_key("gateway.strictn")
check(not ok, "typo 'gateway.strictn' still flagged")
ok, _ = _validate_config_key("stt.enabled")
check(ok, "sanity: 'stt.enabled' still recognized")

print()
print(f"RESULT: {passed} passed / {failed} failed")
sys.exit(1 if failed else 0)
