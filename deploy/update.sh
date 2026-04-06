#!/bin/bash
set -e

echo "=== AI记忆实验平台 - 更新脚本 ==="
echo "时间: $(date)"
echo ""

# 检查当前目录
if [ ! -f "docker-compose.yml" ]; then
    echo "错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 加载环境变量
if [ -f ".env.production" ]; then
    source .env.production
    echo "加载环境变量: .env.production"
else
    echo "错误: .env.production 文件不存在"
    exit 1
fi

echo "1. 检查Git状态..."
if [ -d ".git" ]; then
    echo "   Git仓库存在，拉取最新代码..."
    git fetch origin
    LOCAL=$(git rev-parse @)
    REMOTE=$(git rev-parse @{u})

    if [ "$LOCAL" = "$REMOTE" ]; then
        echo "   代码已是最新"
    else
        echo "   发现新版本，更新代码..."
        git pull origin main
    fi
else
    echo "   警告: 非Git仓库，跳过代码更新"
fi

echo ""
echo "2. 备份数据库..."
if [ -f "deploy/backup-postgres.sh" ]; then
    ./deploy/backup-postgres.sh
    echo "   数据库备份完成"
else
    echo "   警告: 备份脚本不存在，跳过数据库备份"
fi

echo ""
echo "3. 停止服务..."
docker-compose down

echo ""
echo "4. 重建镜像..."
docker-compose build --no-cache

echo ""
echo "5. 启动服务..."
docker-compose up -d

echo ""
echo "6. 等待服务启动..."
echo "   等待30秒..."
sleep 30

echo ""
echo "7. 运行健康检查..."
if [ -n "$DOMAIN_NAME" ]; then
    HEALTH_URL="https://$DOMAIN_NAME/health"
else
    HEALTH_URL="http://localhost:8000/health"
fi

if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
    echo "   健康检查成功"
    echo "   应用状态: 正常"
else
    echo "   健康检查失败"
    echo "   尝试本地检查..."

    if curl -s -f "http://localhost:8000/health" > /dev/null 2>&1; then
        echo "   本地健康检查成功"
    else
        echo "   错误: 应用启动失败"
        docker-compose logs app
        exit 1
    fi
fi

echo ""
echo "8. 检查各服务状态..."
echo "   应用容器:"
docker-compose ps app

echo ""
echo "   数据库容器:"
docker-compose ps db

echo ""
echo "   Nginx容器:"
docker-compose ps nginx

echo ""
echo "9. 运行系统监控..."
if [ -f "deploy/monitor.sh" ]; then
    ./deploy/monitor.sh | tail -20
fi

echo ""
echo "=== 更新完成 ==="
echo "时间: $(date)"
echo ""
echo "验证步骤:"
echo "  1. 访问 https://$DOMAIN_NAME (如果已配置域名)"
echo "  2. 测试用户登录功能"
echo "  3. 测试AI对话功能"
echo "  4. 检查后台任务是否正常"
echo ""
echo "如果遇到问题:"
echo "  docker-compose logs -f app    # 查看应用日志"
echo "  docker-compose restart app    # 重启应用"
echo "  ./deploy/monitor.sh           # 查看系统状态"
echo ""
echo "回滚方法:"
echo "  1. 恢复数据库备份:"
echo "     gunzip -c backups/backup_<日期>.sql.gz | docker exec -i ai_memory_postgres psql -U ai_memory -d ai_memory"
echo "  2. 回退到旧版本镜像"
echo "  3. 重启服务: docker-compose up -d"