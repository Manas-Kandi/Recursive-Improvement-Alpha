#!/usr/bin/env python3
"""Replace session.query() with session.exec(select()) across the codebase."""

import re
from pathlib import Path


def replace_queries(text):
    """Replace SQLAlchemy-style session.query() with SQLModel-style session.exec(select())."""
    orig = text

    # Single-line: session.query(X).filter(Y).first()
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(([^)]+)\)\.first\(\)',
        r'session.exec(select(\1).where(\2)).first()',
        text
    )

    # Single-line: session.query(X).filter(Y).all()
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(([^)]+)\)\.all\(\)',
        r'session.exec(select(\1).where(\2)).all()',
        text
    )

    # Single-line: session.query(X).all()
    text = re.sub(
        r'session\.query\(([^)]+)\)\.all\(\)',
        r'session.exec(select(\1)).all()',
        text
    )

    # Single-line: session.query(X).first()
    text = re.sub(
        r'session\.query\(([^)]+)\)\.first\(\)',
        r'session.exec(select(\1)).first()',
        text
    )

    # Multi-line filter with single condition: session.query(X).filter(\n    Cond\n).first()
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(\n(\s+)([^,)]+)\n\s*\)\.first\(\)',
        r'session.exec(select(\1).where(\n\2\3\n\2)).first()',
        text
    )

    # Multi-line filter with single condition: session.query(X).filter(\n    Cond\n).all()
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(\n(\s+)([^,)]+)\n\s*\)\.all\(\)',
        r'session.exec(select(\1).where(\n\2\3\n\2)).all()',
        text
    )

    # Multi-line filter with comma conditions: session.query(X).filter(\n    A,\n    B\n).first()
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(\n(\s+)([^)]+,)\n(\s+)([^)]+)\n\s*\)\.first\(\)',
        r'session.exec(select(\1).where(\n\2\3\n\4\5\n\2)).first()',
        text
    )

    # Multi-line filter with comma conditions: session.query(X).filter(\n    A,\n    B\n).all()
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(\n(\s+)([^)]+,)\n(\s+)([^)]+)\n\s*\)\.all\(\)',
        r'session.exec(select(\1).where(\n\2\3\n\4\5\n\2)).all()',
        text
    )

    # Multi-line filter + order_by + limit + first
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(\n(\s+)([^)]+,)\n(\s+)([^)]+)\n\s*\)\.order_by\(([^)]+)\)\.limit\((\d+)\)\.first\(\)',
        r'session.exec(select(\1).where(\n\2\3\n\4\5\n\2).order_by(\6).limit(\7)).first()',
        text
    )

    # Multi-line filter + order_by + first
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(\n(\s+)([^)]+,)\n(\s+)([^)]+)\n\s*\)\.order_by\(([^)]+)\)\.first\(\)',
        r'session.exec(select(\1).where(\n\2\3\n\4\5\n\2).order_by(\6)).first()',
        text
    )

    # Single-line filter + order_by + limit + first
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(([^)]+)\)\.order_by\(([^)]+)\)\.limit\((\d+)\)\.first\(\)',
        r'session.exec(select(\1).where(\2).order_by(\3).limit(\4)).first()',
        text
    )

    # Single-line filter + order_by + first
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(([^)]+)\)\.order_by\(([^)]+)\)\.first\(\)',
        r'session.exec(select(\1).where(\2).order_by(\3)).first()',
        text
    )

    # Single-line order_by + limit + all
    text = re.sub(
        r'session\.query\(([^)]+)\)\.order_by\(([^)]+)\)\.limit\((\d+)\)\.all\(\)',
        r'session.exec(select(\1).order_by(\2).limit(\3)).all()',
        text
    )

    # Single-line order_by + all
    text = re.sub(
        r'session\.query\(([^)]+)\)\.order_by\(([^)]+)\)\.all\(\)',
        r'session.exec(select(\1).order_by(\2)).all()',
        text
    )

    # Multi-line order_by + all
    text = re.sub(
        r'session\.query\(([^)]+)\)\.order_by\(\n(\s+)([^)]+)\n\s*\)\.all\(\)',
        r'session.exec(select(\1).order_by(\n\2\3\n\2)).all()',
        text
    )

    # Multi-line filter (single condition) + order_by + limit + first
    text = re.sub(
        r'session\.query\(([^)]+)\)\.filter\(\n(\s+)([^,)]+)\n\s*\)\.order_by\(([^)]+)\)\.limit\((\d+)\)\.first\(\)',
        r'session.exec(select(\1).where(\n\2\3\n\2).order_by(\4).limit(\5)).first()',
        text
    )

    return text, text != orig


def add_import(text):
    """Add 'from sqlmodel import select' if missing."""
    if 'from sqlmodel import select' in text:
        return text
    if 'from sqlmodel import' in text:
        return text.replace('from sqlmodel import', 'from sqlmodel import select,')
    lines = text.split('\n')
    import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('from ') or line.startswith('import '):
            import_idx = i + 1
    lines.insert(import_idx, 'from sqlmodel import select')
    return '\n'.join(lines)


def main():
    files = list(Path("src").rglob("*.py")) + list(Path("tests").rglob("*.py"))
    for fpath in files:
        if 'venv' in str(fpath):
            continue
        text = fpath.read_text()
        new_text, changed = replace_queries(text)
        if changed:
            new_text = add_import(new_text)
            fpath.write_text(new_text)
            print(f"  updated {fpath}")


if __name__ == '__main__':
    main()
