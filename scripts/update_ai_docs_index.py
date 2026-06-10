#!/usr/bin/env python3
"""Regenerate docs/AUTO_PROJECT_INDEX.md for AI/code-maintenance context.

The index excludes secrets, runtime artifacts, caches, logs, generated images,
virtual environments, egg-info, databases, and other large/binary files.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AUTO_PROJECT_INDEX.md"

EXCLUDE_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".venv", "venv", "node_modules", "dist", "build", "htmlcov",
    "autowz.egg-info", "drafts", "tmp_image_test", "tmp_google_image_tests",
    ".claude", "data",
}
EXCLUDE_SUFFIXES = {
    ".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log", ".jpg", ".jpeg",
    ".png", ".gif", ".webp", ".ico", ".pdf",
}
EXCLUDE_FILENAMES = {
    ".env", "image_providers.json", "uvicorn.log", "uvicorn.log.prev2",
    "tmp_test_cover.jpg",
}
MAX_TREE_DEPTH = 4
MAX_TREE_ITEMS = 260

CORE_FILES = [
    "app/main.py",
    "app/api/router.py",
    "app/api/routes/articles.py",
    "app/api/routes/scheduler.py",
    "app/api/routes/health.py",
    "app/core/config.py",
    "app/core/logging.py",
    "app/db/engine.py",
    "app/db/models.py",
    "app/db/crud.py",
    "app/models/schemas.py",
    "app/services/pipeline.py",
    "app/services/collector/search.py",
    "app/services/collector/manager.py",
    "app/services/selector/service.py",
    "app/services/writer/service.py",
    "app/services/humanizer/service.py",
    "app/services/guard/blocklist.py",
    "app/services/guard/service.py",
    "app/services/llm/client.py",
    "app/services/wechat/service.py",
    "app/services/wechat/cover_generator.py",
    "app/services/wechat/mp_backend.py",
    "app/services/wechat/publish_sync.py",
    "app/tasks/scheduler.py",
]


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if path.name in EXCLUDE_FILENAMES:
        return True
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return True
    if any(part.startswith(".env") and part != ".env.example" for part in rel.parts):
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    return False


def summarize_py(rel_path: str) -> tuple[str, str, str]:
    p = ROOT / rel_path
    if not p.exists():
        return "", "", ""
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError as e:
        return f"PARSE ERROR: {e}", "", ""
    defs: list[str] = []
    imports: list[str] = []
    routes: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            defs.append("class " + node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            defs.append("async def " + node.name)
        elif isinstance(node, ast.FunctionDef):
            defs.append("def " + node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                try:
                    s = ast.unparse(dec)
                except Exception:
                    continue
                if "router." in s or "app." in s:
                    routes.append(f"{s} -> {node.name}")
    return "; ".join(defs[:25]), ", ".join(sorted(set(imports))[:25]), "; ".join(routes[:20])


def tree_lines() -> list[str]:
    files: list[str] = []

    def walk(dir_path: Path, depth: int = 0) -> None:
        if depth > MAX_TREE_DEPTH or len(files) >= MAX_TREE_ITEMS:
            return
        try:
            children = sorted(dir_path.iterdir(), key=lambda x: x.name)
        except (PermissionError, OSError):
            return
        for child in children:
            if len(files) >= MAX_TREE_ITEMS:
                return
            if should_skip(child):
                continue
            if child.is_dir():
                walk(child, depth + 1)
            elif child.is_file():
                files.append(child.relative_to(ROOT).as_posix())

    walk(ROOT)
    return files


def main() -> None:
    rows = []
    route_rows = []
    for rel in CORE_FILES:
        defs, imports, routes = summarize_py(rel)
        if defs or imports:
            rows.append((rel, defs or "-", imports or "-"))
        if routes:
            route_rows.append((rel, routes))

    lines: list[str] = []
    lines.append("# 自动/半自动项目索引")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("> 由 `scripts/update_ai_docs_index.py` 生成。已排除 `.env`、真实 provider 配置、日志、数据库、缓存、草稿图片、虚拟环境等。")
    lines.append("")
    lines.append("## 核心 Python 模块摘要")
    lines.append("")
    lines.append("| 文件 | 顶层定义 | 顶层导入 |")
    lines.append("|---|---|---|")
    for rel, defs, imports in rows:
        lines.append(f"| `{rel}` | {defs} | {imports} |")
    lines.append("")
    lines.append("## 路由装饰器索引")
    lines.append("")
    lines.append("| 文件 | 路由 |")
    lines.append("|---|---|")
    for rel, routes in route_rows:
        lines.append(f"| `{rel}` | {routes} |")
    lines.append("")
    lines.append("## 核心文件列表（已排除运行产物）")
    lines.append("")
    lines.append("```text")
    lines.extend(tree_lines())
    lines.append("```")
    lines.append("")
    lines.append("## 主要命令")
    lines.append("")
    lines.append("```bash")
    lines.append("uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    lines.append("python scripts/init_db.py")
    lines.append("pytest tests/ -v")
    lines.append("ruff check app tests scripts")
    lines.append("python scripts/update_ai_docs_index.py")
    lines.append("```")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
