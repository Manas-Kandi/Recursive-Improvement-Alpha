"""Content scaffolds — deterministic expansion of trivial file content.

"Write an index.html with hello world" should produce a real HTML document,
not the literal text "hello world". The scaffold layer infers structure from
the file extension while leaving already-structured content untouched. This is
pure string templating — no LLM involved — in keeping with the harness-first
philosophy.
"""

from pathlib import Path


def expand_content(path: str, content: str) -> str:
    """Expand trivial content into a proper document scaffold by file type.

    Already-structured content (a real HTML document, a Markdown doc with a
    heading, multi-line code) is returned unchanged.
    """
    if not path or content is None:
        return content

    ext = Path(path).suffix.lower()
    stripped = content.strip()

    if ext in (".html", ".htm"):
        return _scaffold_html(path, stripped)
    if ext == ".md":
        return _scaffold_markdown(path, stripped)
    return content


def _looks_like_html_document(content: str) -> bool:
    lowered = content.lower()
    return "<html" in lowered or "<!doctype" in lowered


def _scaffold_html(path: str, content: str) -> str:
    if _looks_like_html_document(content):
        return content
    # If the content already contains markup fragments, embed them verbatim;
    # otherwise present the text as a heading.
    body = content if "<" in content else f"    <h1>{content}</h1>"
    title = Path(path).stem.replace("-", " ").replace("_", " ").title() or "Page"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '    <meta charset="UTF-8">\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"    <title>{title}</title>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _scaffold_markdown(path: str, content: str) -> str:
    if content.startswith("#"):
        return content
    title = Path(path).stem.replace("-", " ").replace("_", " ").title() or "Document"
    return f"# {title}\n\n{content}\n"
