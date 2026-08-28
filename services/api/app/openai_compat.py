from pathlib import Path as _P
_src = "".join(_p.read_text(encoding="utf-8") for _p in sorted((_P(__file__).resolve().parent / "_openai_compat_parts").glob("*.txt")))
exec(compile(_src, __file__, "exec"), globals())
