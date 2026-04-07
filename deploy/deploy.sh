#!/bin/bash
set -e

echo "=== AI记忆实验平台部署脚本 ==="
echo "用法: ./deploy/deploy.sh <域名> <邮箱>"
echo "示例: ./deploy/deploy.sh your-domain.com admin@your-domain.com"
echo ""

DOMAIN_NAME="${1:-your-domain.com}"
CERTBOT_EMAIL="${2:-admin@your-domain.com}"

if [ "$DOMAIN_NAME" = "your-domain.com" ] || [ "$CERTBOT_EMAIL" = "admin@your-domain.com" ]; then
    echo "错误：请提供真实的域名和邮箱"
    echo "示例: ./deploy/deploy.sh your-domain.com admin@your-domain.com"
    exit 1
fi

echo "域名: $DOMAIN_NAME"
echo "邮箱: $CERTBOT_EMAIL"
echo ""

echo "1. 创建目录结构..."
mkdir -p nginx/{conf.d,ssl,logs}
mkdir -p certbot/{www,conf}
mkdir -p backups logs

echo "2. 复制配置文件..."
if [ -f "docker-compose.prod.yml" ]; then
    cp docker-compose.prod.yml docker-compose.yml
    echo "  已复制 docker-compose.prod.yml -> docker-compose.yml"
else
    echo "  错误：docker-compose.prod.yml 不存在"
    exit 1
fi

echo "3. 设置环境变量..."
if [ ! -f ".env.production" ]; then
    echo "  创建生产环境变量文件..."
    cat > .env.production << EOF
# ========================================
# 自动生成的生产环境配置
# ========================================
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
DOMAIN_NAME=$DOMAIN_NAME
CERTBOT_EMAIL=$CERTBOT_EMAIL
DEBUG=False
APP_PORT=8000
SESSION_TTL_HOURS=168
POSTGRES_HOST=db
POSTGRES_DB=ai_memory
POSTGRES_USER=ai_memory
POSTGRES_PORT=5432
MODEL_PROVIDER=qwen
# 请配置以下变量：
QWEN_API_KEY=your-qwen-api-key-from-aliyun
DEEPSEEK_API_KEY=your-deepseek-api-key-backup
# 并发优化配置
WORKERS=4
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
GUNICORN_WORKER_CLASS=gevent
GUNICORN_WORKER_CONNECTIONS=1000
GUNICORN_TIMEOUT=120
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
EOF
    echo "  请编辑 .env.production 文件配置API密钥"
    echo "  重要：配置 QWEN_API_KEY 和 DEEPSEEK_API_KEY"
    exit 1
else
    echo "  使用现有 .env.production 文件"
    # 更新域名和邮箱
    sed -i "s/DOMAIN_NAME=.*/DOMAIN_NAME=$DOMAIN_NAME/" .env.production
    sed -i "s/CERTBOT_EMAIL=.*/CERTBOT_EMAIL=$CERTBOT_EMAIL/" .env.production
fi

source .env.production

echo "4. 处理Nginx配置文件..."
# 替换nginx配置中的域名
if [ -f "nginx/conf.d/ai-memory.conf" ]; then
    cp nginx/conf.d/ai-memory.conf nginx/conf.d/ai-memory.conf.template
    envsubst '${DOMAIN_NAME}' < nginx/conf.d/ai-memory.conf.template > nginx/conf.d/ai-memory.conf
    echo "  已替换nginx配置中的域名"
else
    echo "  错误：nginx/conf.d/ai-memory.conf 不存在"
    exit 1
fi

echo "5. 构建Docker镜像..."
docker-compose build

echo "6. 启动服务..."
docker-compose up -d

echo "7. 等待服务启动..."
echo "   等待30秒..."
sleep 30

echo "8. 初始化数据库..."
if docker exec ai_memory_postgres psql -U ai_memory -d ai_memory -c "SELECT 1" > /dev/null 2>&1; then
    echo "   数据库连接成功"
else
    echo "   数据库连接失败"
    docker-compose logs db
    exit 1
fi

echo "9. 获取SSL证书..."
echo "   运行Certbot获取证书..."
docker-compose run --rm certbot

echo "10. 重启Nginx加载SSL证书..."
docker-compose restart nginx

echo "11. 运行健康检查..."
echo "   等待10秒让服务稳定..."
sleep 10

if curl -f https://$DOMAIN_NAME/health > /dev/null 2>&1; then
    echo "   健康检查成功"
else
    echo "   健康检查失败"
    docker-compose logs app
    exit 1
fi

echo ""
echo "=== 部署完成 ==="
echo "应用地址: https://$DOMAIN_NAME"
echo "管理员账号: admin / psy2025"
echo ""
echo "管理命令:"
echo "  docker-compose logs -f app    # 查看应用日志"
echo "  docker-compose restart app    # 重启应用"
echo "  ./deploy/backup-postgres.sh   # 备份数据库"
echo "  ./deploy/monitor.sh           # 监控系统状态"
echo "  ./deploy/update.sh            # 更新应用"
echo ""
echo "下一步："
echo "  1. 访问 https://$DOMAIN_NAME 验证部署"
echo "  2. 使用管理员账号登录测试功能"
echo "  3. 配置定期备份和监控"