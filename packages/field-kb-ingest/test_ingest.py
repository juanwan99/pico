from ingest import slices_from_markdown


def test_slices_headers_and_paragraphs():
    rows = slices_from_markdown("# 班\n语文,5\n\n说明一段", "课时表")
    assert rows
    assert rows[0]["title"] == "课时表"
    blob = " ".join(r["excerpt"] for r in rows)
    assert "班" in blob or "语文" in blob or "说明" in blob
    assert all(r["excerpt"] for r in rows)


def test_empty_falls_back_to_title():
    rows = slices_from_markdown("  ", "只有名")
    assert rows[0]["excerpt"] == "只有名"
