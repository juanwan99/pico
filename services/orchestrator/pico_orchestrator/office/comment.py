"""Thin OOXML Word comments. Not a track-changes UX."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

from pico_orchestrator.artifact_types import is_valid_ooxml_package

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W = f"{{{W_NS}}}"
CT = f"{{{CT_NS}}}"
REL = f"{{{REL_NS}}}"
COMMENTS_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
COMMENTS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"

ET.register_namespace("w", W_NS)


def add_docx_comment(
    raw: bytes,
    *,
    paragraph_index: int,
    text: str,
    author: str = "Pico",
) -> bytes:
    if not is_valid_ooxml_package(raw, ".docx"):
        raise ValueError("不是真 Word（OOXML）。请上传已有的 .docx。")
    note = (text or "").strip()
    if not note:
        raise ValueError("批注不能为空。")
    if paragraph_index < 1:
        raise ValueError("段落序号从 1 起。")
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        document_xml = zf.read("word/document.xml")
        comments_xml = zf.read("word/comments.xml") if "word/comments.xml" in names else None
        rels_xml = (
            zf.read("word/_rels/document.xml.rels")
            if "word/_rels/document.xml.rels" in names
            else _empty_rels()
        )
        types_xml = zf.read("[Content_Types].xml")
        extras = {name: zf.read(name) for name in names}

    comment_id, comments_xml = _upsert_comments(comments_xml, text=note, author=author)
    document_xml = _mark_paragraph(document_xml, paragraph_index=paragraph_index, comment_id=comment_id)
    rels_xml = _ensure_comments_rel(rels_xml)
    types_xml = _ensure_comments_type(types_xml)

    extras["word/document.xml"] = document_xml
    extras["word/comments.xml"] = comments_xml
    extras["word/_rels/document.xml.rels"] = rels_xml
    extras["[Content_Types].xml"] = types_xml
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in extras.items():
            zf.writestr(name, data)
    data = out.getvalue()
    if not is_valid_ooxml_package(data, ".docx"):
        raise ValueError("加批注后不是真 Word，未保存。")
    return data


def list_docx_comments(raw: bytes) -> list[dict[str, object]]:
    if not is_valid_ooxml_package(raw, ".docx"):
        return []
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        if "word/comments.xml" not in zf.namelist():
            return []
        tree = ET.fromstring(zf.read("word/comments.xml"))
    out: list[dict[str, object]] = []
    for i, node in enumerate(tree.findall(f"{W}comment"), start=1):
        texts = [t.text or "" for t in node.iter(f"{W}t")]
        body = "".join(texts).strip()
        if not body:
            continue
        out.append(
            {
                "index": i,
                "kind": "comment",
                "id": node.get(f"{{{W_NS}}}id") or node.get("id") or str(i),
                "author": node.get(f"{{{W_NS}}}author") or node.get("author") or "",
                "text": body[:240],
            }
        )
    return out


def _empty_rels() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )


def _upsert_comments(existing: bytes | None, *, text: str, author: str) -> tuple[str, bytes]:
    if existing:
        tree = ET.fromstring(existing)
    else:
        tree = ET.Element(f"{W}comments")
    used = 0
    for node in tree.findall(f"{W}comment"):
        raw_id = node.get(f"{{{W_NS}}}id") or node.get("id") or "0"
        try:
            used = max(used, int(raw_id))
        except ValueError:
            continue
    comment_id = str(used + 1 if existing else 0)
    comment = ET.SubElement(tree, f"{W}comment")
    comment.set(f"{{{W_NS}}}id", comment_id)
    comment.set(f"{{{W_NS}}}author", author)
    comment.set(f"{{{W_NS}}}initials", (author[:1] or "P"))
    comment.set(f"{{{W_NS}}}date", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    para = ET.SubElement(comment, f"{W}p")
    run = ET.SubElement(para, f"{W}r")
    t = ET.SubElement(run, f"{W}t")
    t.text = text
    return comment_id, _xml_bytes(tree)


def _mark_paragraph(document_xml: bytes, *, paragraph_index: int, comment_id: str) -> bytes:
    tree = ET.fromstring(document_xml)
    paras = _nonempty_paragraphs(tree)
    if not paras:
        raise ValueError("这份 Word 没有可批注的段落。")
    if paragraph_index > len(paras):
        raise ValueError(f"没有第 {paragraph_index} 段（共 {len(paras)} 段）。")
    para = paras[paragraph_index - 1]
    start = ET.Element(f"{W}commentRangeStart")
    start.set(f"{{{W_NS}}}id", comment_id)
    end = ET.Element(f"{W}commentRangeEnd")
    end.set(f"{{{W_NS}}}id", comment_id)
    ref_run = ET.Element(f"{W}r")
    rpr = ET.SubElement(ref_run, f"{W}rPr")
    style = ET.SubElement(rpr, f"{W}rStyle")
    style.set(f"{{{W_NS}}}val", "CommentReference")
    ref = ET.SubElement(ref_run, f"{W}commentReference")
    ref.set(f"{{{W_NS}}}id", comment_id)
    para.insert(0, start)
    para.append(end)
    para.append(ref_run)
    return _xml_bytes(tree)


def _nonempty_paragraphs(tree: ET.Element) -> list[ET.Element]:
    out: list[ET.Element] = []
    for para in tree.iter(f"{W}p"):
        texts = [t.text or "" for t in para.iter(f"{W}t")]
        if "".join(texts).strip():
            out.append(para)
    return out


def _ensure_comments_rel(rels_xml: bytes) -> bytes:
    tree = ET.fromstring(rels_xml)
    for rel in tree.findall(f"{REL}Relationship"):
        if rel.get("Type") == COMMENTS_REL:
            return rels_xml
    used = {rel.get("Id") or "" for rel in tree.findall(f"{REL}Relationship")}
    rid = "rIdComments"
    n = 1
    while rid in used:
        n += 1
        rid = f"rIdComments{n}"
    rel = ET.SubElement(tree, f"{REL}Relationship")
    rel.set("Id", rid)
    rel.set("Type", COMMENTS_REL)
    rel.set("Target", "comments.xml")
    return _xml_bytes(tree)


def _ensure_comments_type(types_xml: bytes) -> bytes:
    tree = ET.fromstring(types_xml)
    for node in tree.findall(f"{CT}Override"):
        if node.get("PartName") == "/word/comments.xml":
            return types_xml
    node = ET.SubElement(tree, f"{CT}Override")
    node.set("PartName", "/word/comments.xml")
    node.set("ContentType", COMMENTS_TYPE)
    return _xml_bytes(tree)


def _xml_bytes(tree: ET.Element) -> bytes:
    return ET.tostring(tree, encoding="utf-8", xml_declaration=True)
