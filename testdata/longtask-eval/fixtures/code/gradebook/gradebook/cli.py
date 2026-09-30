"""Command line: card / rank / export / summary / notify."""

from __future__ import annotations

import argparse
import sys

from . import export, fmt, loader, notify, ranking, report_card, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gradebook")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("card")
    p.add_argument("csv")
    p.add_argument("sid")
    p = sub.add_parser("rank")
    p.add_argument("csv")
    p.add_argument("cls")
    p.add_argument("subject")
    p = sub.add_parser("export")
    p.add_argument("csv")
    p.add_argument("out")
    p = sub.add_parser("summary")
    p.add_argument("csv")
    p = sub.add_parser("notify")
    p.add_argument("csv")
    p.add_argument("sid")
    args = ap.parse_args(argv)
    students = loader.load_csv(args.csv)
    if args.cmd in ("card", "notify"):
        st = loader.find(students, args.sid)
        if st is None:
            print(f"no student {args.sid}", file=sys.stderr)
            return 1
        print(report_card.render_card(st) if args.cmd == "card" else notify.parent_message(st))
    elif args.cmd == "rank":
        members = loader.by_class(students).get(args.cls, [])
        rows = [["名次", "姓名", "总评", "等级"]]
        for i, (name, score, letter) in enumerate(ranking.rank_class(members, args.subject), 1):
            rows.append([str(i), name, fmt.num(score), letter])
        print(fmt.table(rows))
    elif args.cmd == "export":
        n = export.export_csv(students, args.out)
        print(f"wrote {n} rows to {args.out}")
    else:
        rows = [["班级", "科目", "均分", "及格率"]]
        for cls, info in summary.class_summary(students).items():
            for sub_name, s in info.items():
                rows.append([cls, sub_name, fmt.num(s["mean"]), fmt.pct(s["pass_rate"])])
        print(fmt.table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
