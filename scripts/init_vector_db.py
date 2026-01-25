"""
[已弃用] ChromaDB 版本的向量初始化脚本

该脚本已被 init_memory_vectors.py 替代。

新脚本使用 Numpy + SQLite 实现，更轻量、更稳定。

用法:
    python scripts/init_memory_vectors.py
    python scripts/init_memory_vectors.py --stats
    python scripts/init_memory_vectors.py --test USER_ID "查询内容"
"""

import sys
import os

print("=" * 60)
print("[警告] 此脚本已弃用")
print()
print("请使用新脚本: python scripts/init_memory_vectors.py")
print()
print("新脚本使用 Numpy + SQLite 实现 L4 记忆检索，")
print("无需安装 ChromaDB，更加轻量稳定。")
print("=" * 60)

# 自动调用新脚本
if __name__ == "__main__":
    os.system(f"{sys.executable} scripts/init_memory_vectors.py " + " ".join(sys.argv[1:]))
