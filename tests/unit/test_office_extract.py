from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.office_extract import col_index, extract_office


def _xlsx_bytes(rows: list[list[str]], *, sheet: str = "课时") -> bytes:
    shared = []
    cells_xml = []
    for r, row in enumerate(rows, start=1):
        parts = []
        for c, val in enumerate(row):
            idx = len(shared)
            shared.append(val)
            col = chr(ord("A") + c)
            parts.append(f'<c r="{col}{r}" t="s"><v>{idx}</v></c>')
        cells_xml.append(f'<row r="{r}">{"".join(parts)}</row>')
    sst = "".join(f"<si><t>{escape(s)}</t></si>" for s in shared)
    sheet_xml = (
        '<?xml version="1.0"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(cells_xml)}</sheetData></worksheet>'
    )
    workbook = (
        '<?xml version="1.0"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheets><sheet name="{escape(sheet)}" sheetId="1" r:id="rId1" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        "</sheets></workbook>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"{sst}</sst>",
        )
    return buf.getvalue()


def _docx_bytes(paragraphs: list[str]) -> bytes:
    body = "".join(
        "<w:p>"
        '<w:r><w:t xml:space="preserve">'
        f"{escape(p)}</w:t></w:r></w:p>"
        for p in paragraphs
    )
    document = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document)
    return buf.getvalue()


def test_col_index() -> None:
    assert col_index("A1") == 0
    assert col_index("C12") == 2


def test_xlsx_rows_cols() -> None:
    raw = _xlsx_bytes([["班", "科", "周课时"], ["高一1班", "语文", "5"], ["高一2班", "语文", "4"]])
    got = extract_office("课时.xlsx", raw)
    assert got["status"] == "ok"
    assert got["rows"] == 3
    assert got["cols"] == 3
    assert got["headline"] == "读到 3 行 / 3 列"
    assert "语文" in got["text"]
    assert "5" in got["text"]


def test_docx_paragraphs() -> None:
    got = extract_office("说明.docx", _docx_bytes(["本学期课时", "语文每周 5 节"]))
    assert got["status"] == "ok"
    assert got["headline"] == "读到 2 段"
    assert "语文每周 5 节" in got["text"]


def test_csv() -> None:
    got = extract_office("a.csv", "班,科\n一班,语\n".encode())
    assert got["headline"] == "读到 2 行 / 2 列"


def test_bad_xlsx() -> None:
    got = extract_office("坏.xlsx", b"not-a-zip")
    assert got["status"] == "bad_file"
    assert "坏文件" in got["error"]


def test_unsupported_xls() -> None:
    got = extract_office("old.xls", b"abcd")
    assert got["status"] == "unsupported"
