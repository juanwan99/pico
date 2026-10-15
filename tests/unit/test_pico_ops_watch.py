"""pico#1273 · scripts/pico_ops_watch.py: causes, .env trail, alert state machine."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pico_ops_watch.py"


@pytest.fixture()
def watch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name, value in {
        "PICO_OPS_STATE": tmp_path / "state.json",
        "PICO_OPS_LOG": tmp_path / "watch.log",
        "PICO_OPS_ENV": tmp_path / ".env",
        "PICO_OPS_ENV_TRAIL": tmp_path / "trail.log",
        "PICO_OPS_ENV_SNAPSHOT": tmp_path / "env.snapshot",
        "PICO_OPS_ALERT": tmp_path / "no-alert.py",
    }.items():
        monkeypatch.setenv(name, str(value))
    spec = importlib.util.spec_from_file_location("pico_ops_watch", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mails: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "mail", lambda subject, body: mails.append((subject, body)) or "sent")
    mod.sent = mails
    return mod


def test_causes_group_live_error_texts(watch) -> None:
    cases = {
        "模型调用失败：Error code: 403 - {'error': {'message': 'API密钥已被暂停，请联系管理员'": "钥被停 / 无权限",
        "OpenAI API error (429): too many requests": "上游限流 429",
        "模型调用失败：Error code: 502 - {'error': {'message': 'URLError'": "上游 5xx / 连不上",
        "模型不可用：gpt-5.6-sol。请检查 DEEPSEEK_MODEL": "模型不可用",
        "Stream ended without finish_reason": "流断 / 空输出",
        "本轮声称已交文件，但没有可下载的真文件。": "没交出文件",
        "runner refused: runner.workspace_busy": "对话占用中",
        "深度模式长时间无有效进展，已触发熔断": "无进展熔断",
        "Cannot read properties of undefined (reading 'startsWith')": "代码错误",
        "something new": "其他",
    }
    for text, want in cases.items():
        assert watch.cause_of(text) == want, text


def test_runs_rate_leaves_teacher_cancels_out(watch) -> None:
    rows = [["succeeded", 0, "", "m"]] * 6 + [
        ["failed", 0, "Error code: 502 URLError", "m"],
        ["failed", 0, "Error code: 502 URLError", "m"],
        ["cancelled", 0, "", "m"],  # system cancel counts
        ["cancelled", 1, "", "m"],  # the teacher pressed stop: not a failure
    ]
    ok, bad, user_cancel, causes = watch.summarize_runs(rows)
    assert (ok, bad, user_cancel) == (6, 3, 1)
    assert {k: len(v) for k, v in causes.items()} == {"上游 5xx / 连不上": 2, "系统取消": 1}


def test_env_trail_masks_secrets_and_moves_snapshot(watch, tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("PICO_HEDGE_FAST_S=1.5\nDEEPSEEK_API_KEY=sk-old\n", encoding="utf-8")
    assert watch.record_env("", "", "watch") == []  # first run = baseline only
    env.write_text("PICO_HEDGE_FAST_S=25\nDEEPSEEK_API_KEY=sk-new\nPICO_NEW=1\n", encoding="utf-8")
    changes = watch.record_env("pico#1269", "cancel legs 60 %", "env-record")
    assert "PICO_HEDGE_FAST_S: 1.5 -> 25" in changes
    assert "PICO_NEW: unset -> 1" in changes
    trail = (tmp_path / "trail.log").read_text(encoding="utf-8")
    assert "pico#1269" in trail and "cancel legs 60 %" in trail
    assert "sk-old" not in trail and "sk-new" not in trail and "DEEPSEEK_API_KEY: sha:" in trail
    assert watch.record_env("pico#1269", "again", "env-record") == []  # nothing new


def test_unlogged_env_change_alerts_once(watch, tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("A=1\n", encoding="utf-8")
    assert watch.check_env({})[0] is False
    env.write_text("A=2\n", encoding="utf-8")
    bad, _summary, detail = watch.check_env({})
    assert bad and "A: 1 -> 2" in detail
    assert "UNLOGGED" in (tmp_path / "trail.log").read_text(encoding="utf-8")
    assert watch.check_env({})[0] is False  # recorded; next round is clean


def test_env_set_backs_up_edits_and_trails(watch, tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# keep\nA=1\nB=2\n", encoding="utf-8")
    watch.record_env("", "", "watch")
    watch.cmd_env_set(["B=3", "C=4"], "pico#1273", "drill")
    assert env.read_text(encoding="utf-8") == "# keep\nA=1\nB=3\nC=4\n"
    assert list(tmp_path.glob(".env.bak.pico1273-*"))
    assert "B: 2 -> 3; C: unset -> 4" in (tmp_path / "trail.log").read_text(encoding="utf-8")


def _only(watch, monkeypatch: pytest.MonkeyPatch, result: list) -> None:
    monkeypatch.setattr(watch, "CHECKS", {"disk": lambda state: tuple(result)})


def test_alert_once_remind_after_6h_and_recover(watch, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    result = [True, "根盘 86%", ""]
    _only(watch, monkeypatch, result)
    watch.cmd_check(None)
    watch.cmd_check(None)
    assert [s for s, _ in watch.sent] == ["[pico] 告警：disk"]  # second bad round: no repeat

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    old = (dt.datetime.now().astimezone() - dt.timedelta(hours=7)).isoformat(timespec="seconds")
    state["checks"]["disk"]["last_mail"] = old
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    watch.cmd_check(None)
    assert len(watch.sent) == 2  # still bad after 6 h: reminder

    result[:] = [False, "根盘 70%", ""]
    watch.cmd_check(None)
    assert watch.sent[-1][0] == "[pico] 恢复：disk"
    watch.cmd_check(None)
    assert len(watch.sent) == 3


def test_drill_mails_without_touching_state(watch, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _only(watch, monkeypatch, [False, "根盘 70%", ""])
    watch.cmd_check("disk")
    assert watch.sent[0][0] == "[pico] 演练：disk" and "【演练】" in watch.sent[0][1]
    assert not (tmp_path / "state.json").exists()


def test_broken_check_is_itself_an_alert(watch, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(state):
        raise RuntimeError("docker gone")

    monkeypatch.setattr(watch, "CHECKS", {"runs": boom})
    watch.cmd_check(None)
    assert watch.sent and "检查本身出错" in watch.sent[0][1]


def test_disk_band_does_not_flap(watch, monkeypatch: pytest.MonkeyPatch) -> None:
    class Usage:
        def __init__(self, used: int, free: int) -> None:
            self.used, self.free, self.total = used, free, used + free

    monkeypatch.setattr(watch.shutil, "disk_usage", lambda p: Usage(84, 16))
    assert watch.check_disk({})[0] is False
    assert watch.check_disk({"checks": {"disk": {"bad": True}}})[0] is True  # 84 ≥ 85 - 2
    monkeypatch.setattr(watch.shutil, "disk_usage", lambda p: Usage(82, 18))
    assert watch.check_disk({"checks": {"disk": {"bad": True}}})[0] is False


def test_upstream_counts_codes_and_channel_reasons(watch, monkeypatch: pytest.MonkeyPatch) -> None:
    log = (
        "[GIN] 2026/10/15 - 09:29:25 | relay | id1 | 403 |   90ms |  127.0.0.1 |    POST /v1/chat/completions\n"
        "[GIN] 2026/10/15 - 09:29:26 | relay | id2 | 200 |   90ms |  127.0.0.1 |    POST /v1/chat/completions\n"
        "[GIN] 2026/10/15 - 09:29:27 | relay | id3 | 429 |   90ms |  127.0.0.1 |    POST /v1/chat/completions\n"
        "[ERR] 2026/10/15 - 09:29:26 | id1 | channel error (channel #3, status code: 403): API密钥已被暂停\n"
    )

    class Done:
        stdout, stderr = log, ""

    monkeypatch.setattr(watch.subprocess, "run", lambda *a, **k: Done())
    state: dict = {}
    bad, summary, detail = watch.check_upstream(state)
    assert bad  # a 403 means a person has to act
    assert "403×1" in summary and "429×1" in summary and "200" not in summary
    assert "渠道 #3 403 ×1" in detail
    assert state["upstream_since"]
