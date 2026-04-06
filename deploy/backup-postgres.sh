#!/bin/bash

# 数据库备份脚本
# 使用方法: ./deploy/backup-postgres.sh
# 定时任务: 0 2 * * * /path/to/deploy/backup-postgres.sh

set -e

BACKUP_DIR="../backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="ai_memory"
CONTAINER_NAME="ai_memory_postgres"

echo "=== 数据库备份 ==="
echo "时间: $(date)"
echo "数据库: $DB_NAME"
echo "备份目录: $BACKUP_DIR"
echo ""

# 检查备份目录
if [ ! -d "$BACKUP_DIR" ]; then
    echo "创建备份目录: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# 检查Docker容器
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "错误: 容器 $CONTAINER_NAME 未运行"
    exit 1
fi

echo "开始备份..."
docker exec "$CONTAINER_NAME" pg_dump -U ai_memory "$DB_NAME" > "$BACKUP_DIR/backup_$DATE.sql"

# 检查备份是否成功
if [ $? -eq 0 ] && [ -s "$BACKUP_DIR/backup_$DATE.sql" ]; then
    echo "备份成功: $BACKUP_DIR/backup_$DATE.sql"

    # 压缩备份文件
    echo "压缩备份文件..."
    gzip "$BACKUP_DIR/backup_$DATE.sql"

    # 备份大小
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/backup_$DATE.sql.gz" | cut -f1)
    echo "备份大小: $BACKUP_SIZE"
else
    echo "错误: 备份失败"
    rm -f "$BACKUP_DIR/backup_$DATE.sql"
    exit 1
fi

# 保留最近7天备份
echo "清理旧备份（保留最近7天）..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete

# 统计备份文件
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "*.sql.gz" | wc -l)
echo "当前备份文件数: $BACKUP_COUNT"

echo ""
echo "=== 备份完成 ==="
echo "备份文件: $BACKUP_DIR/backup_$DATE.sql.gz"
echo "备份时间: $(date)"
echo ""