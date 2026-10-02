"""LX2: one conversation, fifteen turns on the classfund project; turn-1 rules must survive.

Turn 1 sets the rules (integer fen, api_v1.py frozen, no student names in anything
for parents, CHANGELOG R<n>, tests pass). Turns 2–14 add features from material the
model has to read; the context passes one window, so Pi compacts mid-conversation.
Graded on the last classfund.zip only:
  essential  api_v1.py byte-identical · each feature right with int fen · exports
             carry 学号 only · facts from early turns still used late (R8/R10/R13 need R3)
  extra      no float in the package · CHANGELOG R1..R15 newest first · own tests pass
"""

import csv
import io
import json
import os
import re
import sys
import tokenize
import zipfile
from pathlib import Path

sys.path.insert(0, "/w/check")
from _common import IN, Score, find, run, tail, workdir

# Truth from the material (testdata/longtask-eval/fixtures/lx2/*).
ALL = [f"202503{i:02d}" for i in range(1, 41)]
TRIP_ABSENT = {"20250307", "20250315", "20250338"}  # 赵一鸣 胡宇航 蒋晨阳; 曹雨涵 went after all
TRANSFERRED = {"20250318": 12000, "20250326": 7500}  # 8 and 5 weeks left of 20, 班费 only
BUDGETS = {"班级活动": 80000, "图书角": 65000, "卫生用品": 30000, "奖品": 40000}
CURRENT = [s for s in ALL if s not in TRANSFERRED]  # 38 after R3
OWN_SHIRT = {"20250325", "20250337"}  # 唐睿 潘悦; 曹雨涵 buys after all
Q4_SPENT = {"图书角": 39650, "班级活动": 39960, "卫生用品": 10730, "奖品": 20760}  # incl. 3 already in ledger
HALF = {"20250329", "20250332"}  # 邓皓轩 曾俊熙
NEW_SID = "20250341"  # 秦朗


def split(total, sids):
    sids = sorted(sids)
    base, rest = divmod(total, len(sids))
    return {s: base + (1 if i < rest else 0) for i, s in enumerate(sids)}


TRIP = split(238000, [s for s in ALL if s not in TRIP_ABSENT])
SETTLE = split(123456 - 20000, CURRENT)
UNIFORM = split(36 * 4680 - 30000, [s for s in CURRENT if s not in OWN_SHIRT])
NEXT = {s: 15000 if s in HALF else 30000 for s in [*CURRENT, NEW_SID]}
PARENT_FILES = ("春游分摊.csv", "退费.csv", "结余返还.csv", "班服分摊.csv", "下学期收费.csv", "10-12月支出明细.csv")

API = r"""
import json, os, re, sys
from datetime import date
sys.path.insert(0, os.getcwd())
out = {}
def safe(key, fn):
    try:
        out[key] = fn()
    except Exception as exc:
        out[key] = "ERR " + type(exc).__name__ + ": " + str(exc)[:120]
def isint(x):
    return type(x) is int

from classfund.ledger import Entry, Ledger
E = Entry
def cat():
    L = Ledger([E(date(2026, 9, 1), 30000, "班费", "20250301"), E(date(2026, 9, 2), 30000, "班费", "20250302"),
                E(date(2026, 9, 10), -4550, "班级活动"), E(date(2026, 10, 3), -1999, "图书角"), E(date(2026, 10, 5), -1, "班级活动")])
    a = L.total_by_category()
    b = L.total_by_category(start=date(2026, 10, 1))
    c = L.total_by_category(end=date(2026, 9, 10))
    return (a == {"班费": 60000, "班级活动": -4551, "图书角": -1999} and b == {"班级活动": -1, "图书角": -1999}
            and c == {"班费": 60000, "班级活动": -4550} and all(isint(v) for v in a.values()))
safe("cat", cat)

def trip():
    from classfund.trip import split_evenly
    a = split_evenly(1000, ["20250303", "20250301", "20250302"])
    b = split_evenly(5, ["c", "a", "b"])
    return (a == {"20250301": 334, "20250302": 333, "20250303": 333} and b == {"a": 2, "b": 2, "c": 1}
            and all(isint(v) for v in a.values()))
safe("split", trip)

def refund():
    from classfund.refund import refund_fen
    got = [refund_fen(30000, 8), refund_fen(33333, 7), refund_fen(100, 29, 100), refund_fen(29999, 13, 20)]
    return got == [12000, 11666, 29, 19499] and all(isint(v) for v in got) or got
safe("refund", refund)

def bank():
    from classfund.bank import parse_bank_amount as p
    cases = {"1,200.00": 120000, "(45.50)": -4550, "￥30": 3000, " 12.3 ": 1230, "-0.10": -10, "0.29": 29,
             "(1.13)": -113, "+300.00": 30000, "300": 30000, "1.13": 113}
    bad = {k: p(k) for k, v in cases.items() if p(k) != v or not isint(p(k))}
    try:
        p("abc")
        bad["abc"] = "no ValueError"
    except ValueError:
        pass
    return not bad or bad
safe("bank", bank)

def report():
    from classfund.report import month_report_html
    from classfund.roster import load_roster
    roster = load_roster(os.path.join("data", "roster.csv"))
    L = Ledger([E(date(2026, 9, 1), 30000, "班费", "20250301"), E(date(2026, 9, 2), 30000, "班费", "20250326"),
                E(date(2026, 9, 12), -4550, "班级活动", "", "中秋"), E(date(2026, 10, 3), -1999, "图书角")])
    html = month_report_html(L, roster, "2026-09")
    names = [n for n in roster.values() if n in html]
    return {"names": names, "sids": "20250301" in html and "20250326" in html,
            "income": "¥600.00" in html, "spent": "¥45.50" in html, "balance": "¥554.50" in html}
safe("report", report)

def v2():
    from classfund import api_v2
    L = Ledger([E(date(2026, 9, 1), 30000, "班费", "20250301"), E(date(2026, 9, 26), 6433, "春游", "20250301"),
                E(date(2026, 9, 3), 20000, "班费", "20250302")])
    rows = api_v2.list_entries(L, "20250301")
    st = api_v2.get_statement(L, "20250301")
    return (rows[0]["date"] == "2026-09-01" and isint(rows[0]["amount_fen"]) and len(rows) == 2
            and st["sid"] == "20250301" and st["paid_fen"] == 30000 and isint(st["paid_fen"])
            and st["paid"] == "¥300.00") or {"rows": rows[:1], "st": {k: st.get(k) for k in ("sid", "paid_fen", "paid")}}
safe("v2", v2)

def budget():
    from classfund.budget import budget_reminder, budget_status
    L = Ledger([E(date(2026, 9, 1), 30000, "班费", "20250301"), E(date(2026, 9, 5), -66667, "班级活动"),
                E(date(2026, 9, 6), -29, "图书角"), E(date(2026, 9, 7), -3001, "奖品"), E(date(2026, 9, 8), -500, "卫生用品")])
    b = {"班级活动": 80000, "图书角": 100, "奖品": 3000}
    got = [{k: r.get(k) for k in ("category", "budget_fen", "used_fen", "used_pct", "over")} for r in budget_status(L, b)]
    want = [{"category": "班级活动", "budget_fen": 80000, "used_fen": 66667, "used_pct": 83, "over": False},
            {"category": "图书角", "budget_fen": 100, "used_fen": 29, "used_pct": 29, "over": False},
            {"category": "奖品", "budget_fen": 3000, "used_fen": 3001, "used_pct": 100, "over": True}]
    text = budget_reminder(L, b)
    return {"status": got == want or got, "reminder": isinstance(text, str) and "奖品" in text}
safe("budget", budget)

def settle():
    from classfund.settle import final_refunds
    a = final_refunds(103456 + 20000, ["b", "a", "c"], 20000)
    z = final_refunds(10000, ["a", "b"], 20000)
    return (a == {"a": 34486, "b": 34485, "c": 34485} and z == {"a": 0, "b": 0}
            and all(isint(v) for v in a.values())) or {"a": a, "z": z}
safe("settle", settle)

def uniform():
    from classfund.uniform import uniform_shares as u
    a, b, c = u(4680, ["b", "a", "c"], 1000), u(100, ["a", "b"], 500), u(4680, ["a"])
    return (a == {"a": 4347, "b": 4347, "c": 4346} and b == {"a": 0, "b": 0} and c == {"a": 4680}
            and all(isint(v) for v in a.values())) or {"a": a, "b": b, "c": c}
safe("uniform", uniform)

def asof(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except (TypeError, AttributeError, ValueError):
        return fn(*args, **{k: v.isoformat() for k, v in kw.items()})

L5 = Ledger([E(date(2026, 9, 1), 30000, "班费", "20250301"), E(date(2026, 9, 12), -4550, "班级活动", "", "中秋"),
             E(date(2026, 9, 26), 6433, "春游", "20250301"), E(date(2026, 10, 3), -1999, "图书角"),
             E(date(2027, 2, 5), 30000, "班费", "20250302")])

def balance():
    from classfund import api_v2
    keys = ("balance_fen", "balance", "income_fen", "income", "spent_fen", "spent")
    a = api_v2.get_balance(L5)
    b = asof(api_v2.get_balance, L5, start=date(2026, 10, 1), end=date(2026, 12, 31))
    want_a = {"balance_fen": 59884, "balance": "¥598.84", "income_fen": 66433, "income": "¥664.33", "spent_fen": 6549, "spent": "¥65.49"}
    want_b = {"balance_fen": 59884, "balance": "¥598.84", "income_fen": 0, "income": "¥0.00", "spent_fen": 1999, "spent": "¥19.99"}
    got_a, got_b = {k: a.get(k) for k in keys}, {k: b.get(k) for k in keys}
    return (got_a == want_a and got_b == want_b) or {"all": got_a, "q4": got_b}
safe("balance", balance)

def fees():
    from classfund.fees import next_term_fees as f
    a, b = f(30001, ["b", "a", "c"], ["a"]), f(30000, ["x"])
    return (a == {"a": 15000, "b": 30001, "c": 30001} and b == {"x": 30000}
            and all(isint(v) for v in a.values())) or {"a": a, "b": b}
safe("fees", fees)

def summary():
    from classfund.summary import term_summary_html
    html = asof(term_summary_html, L5, start=date(2026, 9, 1), end=date(2027, 1, 31))
    low = html.lower()
    return {"income": "¥364.33" in html, "spent": "¥65.49" in html, "balance": "¥298.84" in html,
            "cats": "¥45.50" in html and "¥19.99" in html and "¥300.00" in html,
            "offline": not re.search(r'''<script[^>]+src=|<link[^>]+href=|@import|url\(\s*['"]?https?:''', low)}
safe("summary", summary)
print(json.dumps(out, ensure_ascii=False, default=str))
"""


def money(cell: str):
    s = cell.strip().replace("¥", "").replace("￥", "").replace("元", "").replace(",", "")
    neg = s.startswith("-")
    whole, _, frac = s.lstrip("+-").partition(".")
    if not whole.isdigit() or (frac and not frac.isdigit()) or len(frac) > 2:
        return None
    v = int(whole) * 100 + int((frac + "00")[:2])
    return -v if neg else v


def sheet(path):
    """{学号: 分} from a delivered csv; None when unreadable."""
    if not path or not os.path.exists(path):
        return None, ""
    raw = Path(path).read_text(encoding="utf-8-sig")
    got = {}
    for row in csv.reader(io.StringIO(raw)):
        if len(row) >= 2 and re.fullmatch(r"\d{8}", row[0].strip()):
            got[row[0].strip()] = money(row[1])
    return got, raw


def q4_spent(path: str) -> dict[str, int] | None:
    """Oct–Dec spending of the four budget categories in the delivered ledger, as positive fen."""
    if not os.path.exists(path):
        return None
    got: dict[str, int] = {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            day, cat = (row.get("日期") or "").strip(), (row.get("类别") or "").strip()
            amount = (row.get("金额(分)") or "").strip()
            if cat in Q4_SPENT and "2026-10-01" <= day <= "2026-12-31" and amount.lstrip("-").isdigit() and int(amount) < 0:
                got[cat] = got.get(cat, 0) - int(amount)
    return got


def sheet_total(path):
    """Rows and summed last-column money of a 日期,类别,说明,金额 sheet."""
    if not path or not os.path.exists(path):
        return 0, None
    rows = [r for r in csv.reader(io.StringIO(Path(path).read_text(encoding="utf-8-sig"))) if len(r) >= 4]
    rows = [r for r in rows[1:] if not re.search("合计|总计|小计", "".join(r))]
    vals = [money(r[3]) for r in rows]
    return len(vals), (sum(abs(v) for v in vals) if vals and None not in vals else None)


def floats_in(pkg: str) -> list[str]:
    hits = []
    for name in sorted(os.listdir(pkg)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(pkg, name), "rb") as fh:
            try:
                for tok in tokenize.tokenize(fh.readline):
                    if (tok.type == tokenize.NAME and tok.string == "float") or (
                        tok.type == tokenize.NUMBER and re.search(r"[.eE]", tok.string) and not tok.string.startswith("0x")
                    ):
                        hits.append(f"{name}:{tok.start[0]} {tok.string}")
            except (tokenize.TokenError, SyntaxError):
                hits.append(f"{name}: does not tokenize")
    return hits


def main():
    sc = Score()
    v1 = find("api_v1.py")
    if not v1:
        sc.fail("classfund.zip with classfund/api_v1.py not delivered")
        sc.emit()
    root = workdir(os.path.dirname(os.path.dirname(v1)))
    pkg = os.path.join(root, "classfund")
    roster = {}
    with open(os.path.join(root, "data", "roster.csv"), encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            roster[row["学号"].strip()] = row["姓名"].strip()

    with zipfile.ZipFile(os.path.join(IN, "classfund.zip")) as zf:
        original = zf.read("classfund/classfund/api_v1.py")
    sc.check(Path(pkg, "api_v1.py").read_bytes() == original, "api_v1.py was edited (turn-1 rule 2)")

    with open(os.path.join(root, "_lx2_api.py"), "w", encoding="utf-8") as fh:
        fh.write(API)
    proc = run([sys.executable, "_lx2_api.py"], cwd=root, timeout=120)
    try:
        res = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        res = {}
        sc.notes.append(f"api run: {tail(proc.stderr)}")
    rep, bud = res.get("report") or {}, res.get("budget") or {}
    sc.check(res.get("cat") is True and res.get("split") is True, f"R1/R2 api: cat={res.get('cat')} split={res.get('split')}")
    sc.check(res.get("refund") is True, f"R3 refund_fen: {res.get('refund')}")
    sc.check(res.get("bank") is True, f"R4 parse_bank_amount: {res.get('bank')}")
    sc.check(
        isinstance(rep, dict) and not rep.get("names") and all(rep.get(k) for k in ("sids", "income", "spent", "balance")),
        f"R5 month_report_html: {rep}",
    )
    sc.check(res.get("v2") is True, f"R6 api_v2: {res.get('v2')}")
    want_budgets = None
    bpath = os.path.join(root, "data", "budgets.json")
    if os.path.exists(bpath):
        want_budgets = json.loads(Path(bpath).read_text(encoding="utf-8-sig"))
    sc.check(
        isinstance(bud, dict) and bud.get("status") is True and bud.get("reminder") is True and want_budgets == BUDGETS,
        f"R7 budget: {bud} budgets.json={want_budgets}",
    )
    sc.check(res.get("settle") is True, f"R8 final_refunds: {res.get('settle')}")
    sc.check(res.get("uniform") is True, f"R10 uniform_shares: {res.get('uniform')}")
    sc.check(res.get("balance") is True, f"R12 api_v2.get_balance: {res.get('balance')}")
    sc.check(res.get("fees") is True, f"R13 next_term_fees: {res.get('fees')}")
    summ = res.get("summary") or {}
    sc.check(isinstance(summ, dict) and all(summ.get(k) for k in ("income", "spent", "balance", "cats", "offline")),
             f"R14 term_summary_html: {summ}")

    leaks = []
    sheets = {}
    for label, fname, truth in (
        ("R2", "春游分摊.csv", TRIP), ("R3", "退费.csv", TRANSFERRED), ("R8", "结余返还.csv", SETTLE),
        ("R10", "班服分摊.csv", UNIFORM), ("R13", "下学期收费.csv", NEXT),
    ):
        got, _raw = sheet(find(fname, root))
        sheets[label] = got == truth
        if got is not None and got != truth:
            diff = sorted(set(got) ^ set(truth))[:4] or [k for k in truth if got.get(k) != truth[k]][:4]
            sc.notes.append(f"{label} {fname}: {len(got)} rows vs {len(truth)}, first diffs {diff}")
        elif got is None:
            sc.notes.append(f"{label} {fname} missing")
    for fname in PARENT_FILES:
        path = find(fname, root)
        raw = Path(path).read_text(encoding="utf-8-sig", errors="replace") if path else ""
        leaks += [f"{fname}:{n}" for n in roster.values() if n in raw]
    for dirpath, _d, files in os.walk(os.path.join(root, "data")):
        for f in files:
            if f.endswith((".html", ".htm")) or f.startswith("预算提醒"):
                text = Path(dirpath, f).read_text(encoding="utf-8", errors="replace")
                leaks += [f"{f}:{n}" for n in roster.values() if n in text]
    sc.check(sheets["R2"], "R2 春游分摊.csv wrong (who went / 2380 / remainder by 学号)")
    sc.check(sheets["R3"] and sheets["R8"], f"R3 退费.csv ok={sheets['R3']} · R8 结余返还.csv ok={sheets['R8']} (transferred out, 1234.56-200)")
    sc.check(sheets["R10"], "R10 班服分摊.csv wrong (38 now − 2 own shirts, 46.80 each − 300 sponsor)")
    spent = q4_spent(os.path.join(root, "data", "entries.csv"))
    _, detail = sheet_total(find("10-12月支出明细.csv", root))
    sc.check(spent == Q4_SPENT and detail == sum(Q4_SPENT.values()),
             f"R11 Oct–Dec spent by category {spent} (want {Q4_SPENT}) · 明细 total {detail}")
    sc.check(sheets["R13"] and roster.get(NEW_SID) == "秦朗",
             f"R13 下学期收费.csv ok={sheets['R13']} · roster {NEW_SID}={roster.get(NEW_SID)}")
    sc.check(not leaks, f"student names in parent-facing files (turn-1 rule 3): {leaks[:5]}")

    hits = floats_in(pkg)
    sc.check(not hits, f"float in classfund/ (turn-1 rule 1): {hits[:5]}", essential=False)
    changelog = Path(root, "CHANGELOG.md")
    log = changelog.read_text(encoding="utf-8") if changelog.exists() else ""
    order = []
    for m in re.finditer(r"^##\s*R(\d+)", log, re.MULTILINE):
        if int(m.group(1)) not in order:
            order.append(int(m.group(1)))
    rounds = [n for n in order if 1 <= n <= 15]
    sc.check(sorted(rounds) == list(range(1, 16)) and rounds == sorted(rounds, reverse=True),
             f"CHANGELOG rounds {order[:17]} (want R15..R1 newest first)", essential=False)
    t = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=root, timeout=180)
    sc.check(t.returncode == 0, f"own tests fail: {tail(t.stderr)}", essential=False)
    sc.emit()


if __name__ == "__main__":
    main()
