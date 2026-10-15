"""pico#1295: sandbox fonts — every font the office skills tell the model to
name must be aliased to an installed font, and the build wiring must stay."""

import re
import runpy
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "services/sandbox_worker/fonts"
DOCKERFILE = (ROOT / "services/sandbox_worker/Dockerfile").read_text(encoding="utf-8")
SKILLS = ROOT / "services/orchestrator/pico_orchestrator/office/skills"
INSTALLED = {"Noto Sans CJK SC", "Noto Serif CJK SC", "Noto Sans Mono CJK SC", "AR PL UKai CN", "Carlito", "Caladea", "DejaVu Serif"}


def _aliases(name: str) -> dict[str, str]:
    root = ET.parse(FONTS / name).getroot()
    out = {}
    for alias in root.iter("alias"):
        fam = alias.findtext("family")
        pref = alias.find("prefer")
        if fam and pref is not None:
            out[fam] = pref.findtext("family")
    return out


def test_skill_named_fonts_are_aliased_to_installed():
    aliases = _aliases("24-pico-cjk.conf")
    assert set(aliases.values()) <= INSTALLED
    named = set()
    for skill in ("docx.md", "pptx.md"):
        text = (SKILLS / skill).read_text(encoding="utf-8")
        named |= set(re.findall(r"宋体|黑体|楷体|仿宋|微软雅黑", text))
    assert named, "skills should name the Windows fonts the teacher has"
    for font in named:
        assert font in aliases, font
    assert aliases["宋体"] == "Noto Serif CJK SC"
    assert aliases["黑体"] == "Noto Sans CJK SC"
    assert aliases["楷体"] == "AR PL UKai CN"
    assert aliases["Calibri"] == "Carlito"


def test_generic_fallback_prefers_noto_cjk():
    for conf in ("24-pico-cjk.conf", "64-pico-cjk-fallback.conf"):
        aliases = _aliases(conf)
        assert aliases["serif"] == "Noto Serif CJK SC"
        assert aliases["sans-serif"] == "Noto Sans CJK SC"


def test_dockerfile_installs_fonts_and_wires_configs():
    for pkg in ("fonts-noto-cjk", "fonts-arphic-ukai", "fonts-crosextra-carlito", "fonts-crosextra-caladea", "fonts-dejavu-core"):
        assert pkg in DOCKERFILE
    # conf files must be world-readable: a 0660 checkout made fontconfig skip them.
    assert "COPY --chmod=0644 services/sandbox_worker/fonts/24-pico-cjk.conf" in DOCKERFILE
    assert "64-pico-cjk-fallback.conf /etc/fonts/conf.d/" in DOCKERFILE
    assert "python /tmp/mpl_cjk_defaults.py" in DOCKERFILE


def test_matplotlib_defaults_patch_rewrites_commented_keys(tmp_path, monkeypatch):
    rc = tmp_path / "matplotlibrc"
    rc.write_text("#font.family:  sans-serif\n#font.sans-serif: DejaVu Sans\n#font.serif: DejaVu Serif\n#axes.unicode_minus: True\n", encoding="utf-8")
    # The test venv has no matplotlib; the script only needs matplotlib_fname().
    monkeypatch.setitem(sys.modules, "matplotlib", types.SimpleNamespace(matplotlib_fname=lambda: str(rc)))
    runpy.run_path(str(FONTS / "mpl_cjk_defaults.py"), run_name="__main__")
    text = rc.read_text(encoding="utf-8")
    assert "#font.sans-serif: Noto Sans CJK SC" in text
    assert "#axes.unicode_minus: False" in text
    assert text.count("font.serif") == 1
