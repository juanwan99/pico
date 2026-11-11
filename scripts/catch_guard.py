#!/usr/bin/env python3
"""CI 挡新增吞错（juanwan99/edu-core#5197 · agent-policy#271，照 edu-core scripts/catch-guard #4450）。

PR 新改的行里出现下面两种写法就报红，没改的旧行不查：
  - 空 except：`except ...: pass` / `...`
  - except 不记原因就走：分支里只有 return 常量（None / 0 / "" / [] / {} …）、continue、break、pass，
    没有 raise、没调任何函数（日志、打印、上报都算记了）
只查 pico 自家的 Python；apps/（librechat）不查。
确有理由不记：在 except 那行行尾写 `# swallow-ok: <原因>`。

  python scripts/catch_guard.py              # 本机：对 origin/main 的分叉点比（含没提交的改动）
  python scripts/catch_guard.py <基准提交>    # 对基准提交比工作区
  CI=1 python scripts/catch_guard.py         # CI：对 HEAD^1 比 HEAD（PR 合并提交的第一个父提交 = 目标分支）
exit 0 过 · 1 有红。
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

SKIP_PREFIXES = ("apps/",)
EXEMPT = "swallow-ok:"
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True)


def changed_lines(root: Path, base: str, head: str | None) -> dict[str, set[int]]:
    """{文件: 新改的行号}；head=None 时比工作区。"""
    args = ["diff", "-U0", "--no-color", "--diff-filter=AMR", base]
    if head:
        args.append(head)
    out: dict[str, set[int]] = {}
    cur: str | None = None
    for line in git(root, *args, "--", "*.py").splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            cur = path[2:] if path.startswith("b/") else None
            if cur and (cur.startswith(SKIP_PREFIXES) or "/node_modules/" in cur):
                cur = None
            continue
        m = HUNK.match(line)
        if m and cur:
            start, count = int(m.group(1)), int(m.group(2) or "1")
            out.setdefault(cur, set()).update(range(start, start + count))
    return out


def _literal(node: ast.AST | None) -> bool:
    if node is None or isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp):
        return _literal(node.operand)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_literal(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(_literal(k) and _literal(v) for k, v in zip(node.keys, node.values))
    return False


def _quiet(stmt: ast.stmt) -> bool:
    if isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return True
    return isinstance(stmt, ast.Return) and _literal(stmt.value)


def swallows(source: str) -> list[tuple[int, str]]:
    """[(except 行号, 说明)]：分支里全是不记原因就走的语句。"""
    lines = source.splitlines()
    hits = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ExceptHandler) or not all(_quiet(s) for s in node.body):
            continue
        if EXEMPT in lines[node.lineno - 1]:
            continue
        kind = "空 except" if all(isinstance(s, (ast.Pass, ast.Expr)) for s in node.body) else (
            "except 不记原因就走"
        )
        hits.append((node.lineno, kind))
    return hits


def check(root: Path, base: str, head: str | None) -> list[str]:
    bad = []
    for path, nums in sorted(changed_lines(root, base, head).items()):
        source = git(root, "show", f"{head}:{path}") if head else (root / path).read_text("utf-8")
        try:
            hits = swallows(source)
        except SyntaxError as e:
            bad.append(f"{path}:{e.lineno}  解析失败 {e.msg}")
            continue
        for lineno, kind in hits:
            if lineno in nums:
                bad.append(
                    f"{path}:{lineno}  {kind}：记下原因（logger / raise），"
                    f"确有理由不记就在行尾写 `# {EXEMPT} <原因>`"
                )
    return bad


def main(argv: list[str]) -> int:
    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    if argv:
        base, head = argv[0], None
    elif os.environ.get("CI"):
        base, head = "HEAD^1", "HEAD"
    else:
        base, head = git(root, "merge-base", "origin/main", "HEAD").strip(), None
    bad = check(root, base, head)
    for b in bad:
        print(b)
    if bad:
        print(f"✗ catch_guard：新改的行里有 {len(bad)} 处吞错")
        return 1
    print("catch_guard ok（新改的行里没有吞错）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
