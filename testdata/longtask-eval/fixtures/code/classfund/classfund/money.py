"""金额工具。全项目金额一律是「分」的整数。"""


def fmt_yuan(fen: int) -> str:
    """1230 -> "¥12.30"，-50 -> "-¥0.50"。"""
    if not isinstance(fen, int):
        raise TypeError(f"金额必须是分的整数，收到 {type(fen).__name__}")
    sign = "-" if fen < 0 else ""
    yuan, rest = divmod(abs(fen), 100)
    return f"{sign}¥{yuan}.{rest:02d}"


def parse_yuan(text: str) -> int:
    """"12.3" / "12.30元" / "¥12" -> 分。只认最多两位小数。"""
    s = text.strip().replace("元", "").replace("¥", "")
    sign = -1 if s.startswith("-") else 1
    s = s.lstrip("+-")
    whole, _, frac = s.partition(".")
    if not whole.isdigit() or (frac and not frac.isdigit()) or len(frac) > 2:
        raise ValueError(f"看不懂的金额：{text!r}")
    return sign * (int(whole) * 100 + int((frac + "00")[:2]))
