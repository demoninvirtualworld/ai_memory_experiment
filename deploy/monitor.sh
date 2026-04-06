#!/bin/bash

# 系统监控脚本
# 使用方法: ./deploy/monitor.sh

echo "========================================="
echo "AI记忆实验平台 - 系统监控"
echo "时间: $(date)"
echo "========================================="

echo ""
echo "=== 容器状态检查 ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep ai_memory

echo ""
echo "=== 容器健康状态 ==="
for container in ai_memory_app ai_memory_postgres ai_memory_nginx; do
    if docker ps | grep -q "$container"; then
        health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "N/A")
        state=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null)
        uptime=$(docker inspect --format='{{.State.StartedAt}}' "$container" 2>/dev/null | cut -d. -f1)
        echo "$container: 状态=$state, 健康=$health, 启动时间=$uptime"
    else
        echo "$container: 未运行"
    fi
done

echo ""
echo "=== 资源使用情况 ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep ai_memory

echo ""
echo "=== 最近错误日志（最后20行）==="
echo "应用日志:"
docker logs ai_memory_app --tail 20 2>&1 | grep -i "error\|exception\|failed\|warning" | tail -5

echo ""
echo "数据库日志:"
docker logs ai_memory_postgres --tail 10 2>&1 | grep -i "error\|fatal" | tail -3

echo ""
echo "Nginx日志:"
docker logs ai_memory_nginx --tail 10 2>&1 | grep -i "error" | tail -3

echo ""
echo "=== 磁盘空间检查 ==="
echo "备份目录:"
if [ -d "../backups" ]; then
    du -sh ../backups
    echo "备份文件数: $(find ../backups -name "*.sql.gz" | wc -l)"
else
    echo "备份目录不存在"
fi

echo ""
echo "日志目录:"
if [ -d "../logs" ]; then
    du -sh ../logs
else
    echo "日志目录不存在"
fi

echo ""
echo "=== 服务可用性检查 ==="
# 检查健康端点
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "应用健康端点: 正常"
else
    echo "应用健康端点: 异常"
fi

# 检查数据库连接
if docker exec ai_memory_postgres pg_isready -U ai_memory -d ai_memory > /dev/null 2>&1; then
    echo "数据库连接: 正常"
else
    echo "数据库连接: 异常"
fi

echo ""
echo "=== 系统资源 ==="
echo "内存使用:"
free -h | grep Mem | awk '{print "总内存: "$2, "已用: "$3, "可用: "$4}'

echo ""
echo "磁盘使用:"
df -h / | tail -1 | awk '{print "根目录: 总空间 "$2, "已用 "$3, "可用 "$4, "使用率 "$5}'

echo ""
echo "CPU负载:"
uptime | awk -F'load average:' '{print "负载: "$2}'

echo ""
echo "=== 网络连接 ==="
echo "监听端口:"
netstat -tlnp 2>/dev/null | grep -E ":(80|443|8000|5432)" | awk '{print "端口 "$4, "-> "$7}' | sort

echo ""
echo "========================================="
echo "监控完成"
echo "========================================="

# 如果有问题，提供建议
echo ""
echo "建议:"
if docker ps | grep -q ai_memory_app; then
    echo "✓ 所有容器都在运行"
else
    echo "✗ 有容器未运行，使用 docker-compose ps 查看详情"
fi

if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ 应用服务正常"
else
    echo "✗ 应用服务异常，使用 docker-compose logs app 查看日志"
fi

echo ""
echo "常用命令:"
echo "  docker-compose logs -f app      # 查看应用日志"
echo "  docker-compose restart app      # 重启应用"
echo "  docker-compose ps               # 查看容器状态"
echo "  docker system prune -f          # 清理Docker资源"