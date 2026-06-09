"""Tests for content scaffolds and the workspace index."""

from pathlib import Path

from siha.agent.scaffolds import expand_content
from siha.agent.workspace_index import build_workspace_index


# ---------- Content scaffolds ----------

def test_html_hello_world_becomes_document():
    result = expand_content("index.html", "hello world")
    assert result.startswith("<!DOCTYPE html>")
    assert "<h1>hello world</h1>" in result
    assert "<title>Index</title>" in result


def test_existing_html_document_untouched():
    doc = "<!DOCTYPE html>\n<html><body>custom</body></html>"
    assert expand_content("page.html", doc) == doc


def test_html_fragment_embedded_verbatim():
    fragment = "<p>already markup</p>"
    result = expand_content("frag.html", fragment)
    assert "<p>already markup</p>" in result
    assert "<h1>" not in result


def test_markdown_gets_title_heading():
    result = expand_content("release-notes.md", "first release")
    assert result.startswith("# Release Notes")
    assert "first release" in result


def test_markdown_with_heading_untouched():
    doc = "# My Doc\n\ncontent"
    assert expand_content("doc.md", doc) == doc


def test_other_extensions_untouched():
    assert expand_content("script.py", "print('hi')") == "print('hi')"
    assert expand_content("data.txt", "hello world") == "hello world"


# ---------- Workspace index ----------

def test_index_empty_for_missing_root(tmp_path):
    assert build_workspace_index(None) == ""
    assert build_workspace_index(tmp_path / "nope") == ""


def test_index_lists_files_and_dirs(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1")
    (tmp_path / "readme.md").write_text("# hi")

    index = build_workspace_index(tmp_path)
    assert "Workspace contents:" in index
    assert "src/" in index
    assert "main.py" in index
    assert "readme.md" in index


def test_index_skips_noise_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "app.js").write_text("//")

    index = build_workspace_index(tmp_path)
    assert ".git" not in index
    assert "node_modules" not in index
    assert "app.js" in index


def test_index_truncates_large_trees(tmp_path):
    for i in range(80):
        (tmp_path / f"file_{i:03}.txt").write_text("x")

    index = build_workspace_index(tmp_path, max_entries=10)
    assert "(truncated)" in index
    assert index.count("file_") == 10
