"""Contract: school jump first hop + human fail (no jest required)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDU = (ROOT / "apps/librechat/api/server/routes/eduSso.js").read_text(encoding="utf-8")
AUTH = (ROOT / "apps/librechat/api/server/services/AuthService.js").read_text(encoding="utf-8")
LOGIN = (ROOT / "apps/librechat/client/src/components/Auth/Login.tsx").read_text(encoding="utf-8")
COPY = (ROOT / "apps/librechat/client/src/utils/getSsoLoginMessage.ts").read_text(encoding="utf-8")


def test_edu_sso_sets_lax_cookies_on_success() -> None:
    assert "sameSite: 'lax'" in EDU
    assert "setAuthTokens(userId, res, null, req, { sameSite: 'lax' })" in EDU


def test_edu_sso_fail_is_human_query_not_password_wall() -> None:
    assert "/login?sso=" in EDU
    assert "ssoFailLocation" in EDU
    assert "auth.expired" in EDU
    assert "already used" in EDU


def test_set_auth_tokens_accepts_lax_without_changing_default() -> None:
    assert "options.sameSite === 'lax' ? 'lax' : 'strict'" in AUTH


def test_login_renders_school_copy_not_password_advice() -> None:
    assert "getSsoLoginMessage" in LOGIN
    assert "ssoMessage" in LOGIN
    assert "过期" in COPY
    assert "用过" in COPY
    assert "密码" not in COPY
