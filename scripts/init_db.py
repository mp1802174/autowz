#!/usr/bin/env python3
"""初始化数据库：创建所有表。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.engine import init_db

if __name__ == "__main__":
    init_db()
    print("数据库表创建完成。")
