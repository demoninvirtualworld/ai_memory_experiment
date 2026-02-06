"""
数据库迁移脚本：添加 L4 动态遗忘曲线字段

新增字段（chat_messages 表）：
- consolidation_g: 固化系数 g_n（默认 1.0）
- recall_count: 召回次数 n（默认 0）
- last_recall_at: 上次召回时间
- emotional_salience: 情感显著性分数（默认 0.0）

运行方式：
    python scripts/migrate_add_dynamic_memory_fields.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

DB_PATH = 'data/experiment.db'


def migrate():
    """执行迁移"""
    engine = create_engine(f'sqlite:///{DB_PATH}')

    # 需要添加的新列
    new_columns = [
        ('consolidation_g', 'FLOAT DEFAULT 1.0'),
        ('recall_count', 'INTEGER DEFAULT 0'),
        ('last_recall_at', 'DATETIME'),
        ('emotional_salience', 'FLOAT DEFAULT 0.0'),
    ]

    with engine.connect() as conn:
        for col_name, col_type in new_columns:
            try:
                sql = f'ALTER TABLE chat_messages ADD COLUMN {col_name} {col_type}'
                conn.execute(text(sql))
                conn.commit()
                print(f"[OK] 添加列: {col_name} ({col_type})")
            except OperationalError as e:
                if 'duplicate column name' in str(e).lower():
                    print(f"[SKIP] 列已存在: {col_name}")
                else:
                    print(f"[ERROR] 添加列 {col_name} 失败: {e}")

    print("\n迁移完成！")


def verify():
    """验证迁移结果"""
    engine = create_engine(f'sqlite:///{DB_PATH}')

    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(chat_messages)"))
        columns = [row[1] for row in result.fetchall()]

        print("\nchat_messages 表当前列：")
        for col in columns:
            print(f"  - {col}")

        # 检查新列是否存在
        expected_new_cols = ['consolidation_g', 'recall_count', 'last_recall_at', 'emotional_salience']
        missing = [col for col in expected_new_cols if col not in columns]

        if missing:
            print(f"\n[WARN] 缺少列: {missing}")
        else:
            print(f"\n[OK] 所有新列都已添加！")


if __name__ == '__main__':
    print("=" * 50)
    print("L4 动态遗忘曲线字段迁移")
    print("=" * 50)

    migrate()
    verify()
