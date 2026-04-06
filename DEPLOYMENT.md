# AI记忆实验平台 - 阿里云ECS部署指南

## 概述

本文档提供AI记忆实验平台在阿里云ECS上的完整部署指南。包括Docker容器化部署、HTTPS配置、生产环境优化等内容。

## 系统要求

- 阿里云ECS实例（推荐配置）：
  - CPU: 2核或更高
  - 内存: 4GB或更高
  - 存储: 系统盘40GB SSD + 数据盘100GB SSD
  - 带宽: 按固定带宽5Mbps起步
- 操作系统: Ubuntu 22.04 LTS 或 Alibaba Cloud Linux 3
- 域名: 已备案的域名（用于HTTPS）

## 部署架构

```
阿里云ECS实例
├── Nginx (443/80) - HTTPS反向代理
├── Flask应用 (8000) - AI记忆实验平台
└── PostgreSQL (5432) - 数据库
```

## 快速开始

### 1. 准备ECS实例

1. 登录阿里云控制台，创建ECS实例
2. 配置安全组，开放端口：
   - 22 (SSH)
   - 80 (HTTP)
   - 443 (HTTPS)
3. 连接到ECS实例

### 2. 初始化系统

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 添加用户到docker组
sudo usermod -aG docker $USER
newgrp docker

# 安装必要工具
sudo apt install -y git curl net-tools
```

### 3. 克隆项目

```bash
git clone <repository-url>
cd ai_memory_experiment
```

### 4. 配置环境变量

```bash
# 复制环境变量模板
cp .env.production .env.production.local

# 编辑配置文件
nano .env.production.local
```

需要配置的关键变量：
- `SECRET_KEY`: 应用密钥（使用 `openssl rand -hex 32` 生成）
- `POSTGRES_PASSWORD`: 数据库密码（使用 `openssl rand -hex 16` 生成）
- `QWEN_API_KEY`: 通义千问API密钥
- `DEEPSEEK_API_KEY`: DeepSeek API密钥（备用）
- `DOMAIN_NAME`: 你的域名
- `CERTBOT_EMAIL`: 证书邮箱

### 5. 运行部署脚本

```bash
# 赋予脚本执行权限
chmod +x deploy/deploy.sh

# 运行部署脚本
./deploy/deploy.sh your-domain.com admin@your-domain.com
```

部署脚本会自动：
1. 创建目录结构
2. 配置Nginx
3. 构建Docker镜像
4. 启动所有服务
5. 获取SSL证书
6. 验证部署

## 详细配置

### 数据库配置

项目使用PostgreSQL作为生产数据库。配置位于 `docker-compose.prod.yml` 的 `db` 服务部分。

关键优化参数：
- `max_connections=200`: 最大连接数
- `shared_buffers=256MB`: 共享缓冲区
- `effective_cache_size=1GB`: 有效缓存大小

### Nginx配置

Nginx作为反向代理，配置位于 `nginx/` 目录：
- `nginx.conf`: 主配置文件
- `conf.d/ai-memory.conf`: 站点配置（自动替换域名）

### SSL证书

使用Let's Encrypt免费证书，通过Certbot自动获取和续期。

## 管理命令

### 日常管理

```bash
# 查看服务状态
docker-compose ps

# 查看应用日志
docker-compose logs -f app

# 查看数据库日志
docker-compose logs -f db

# 重启应用
docker-compose restart app

# 停止所有服务
docker-compose down

# 启动所有服务
docker-compose up -d
```

### 数据库管理

```bash
# 备份数据库
./deploy/backup-postgres.sh

# 进入数据库命令行
docker exec -it ai_memory_postgres psql -U ai_memory -d ai_memory

# 恢复数据库备份
gunzip -c backups/backup_20250101_120000.sql.gz | docker exec -i ai_memory_postgres psql -U ai_memory -d ai_memory
```

### 系统监控

```bash
# 运行系统监控
./deploy/monitor.sh

# 查看资源使用
docker stats

# 查看系统资源
free -h
df -h
```

### 应用更新

```bash
# 更新应用
./deploy/update.sh
```

## 安全加固

### 1. 防火墙配置

```bash
# 配置UFW防火墙
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. SSH安全

```bash
# 禁用root登录
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# 使用密钥认证
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# 重启SSH服务
sudo systemctl restart sshd
```

### 3. 定期更新

创建自动更新脚本 `/etc/cron.weekly/system-update`：

```bash
#!/bin/bash
apt-get update && apt-get upgrade -y
apt-get autoremove -y
docker system prune -f
```

## 故障排除

### 常见问题

#### 1. 证书获取失败

**症状**: Certbot无法获取SSL证书

**解决方法**:
```bash
# 检查域名解析
nslookup your-domain.com

# 检查80端口是否开放
sudo netstat -tlnp | grep :80

# 查看Certbot日志
docker-compose logs certbot

# 手动获取证书
docker-compose run --rm certbot certonly --webroot -w /var/www/certbot --email admin@your-domain.com -d your-domain.com --agree-tos --no-eff-email
```

#### 2. 数据库连接失败

**症状**: 应用无法连接到PostgreSQL

**解决方法**:
```bash
# 检查数据库容器状态
docker-compose ps db

# 查看数据库日志
docker-compose logs db

# 测试数据库连接
docker exec ai_memory_postgres pg_isready -U ai_memory -d ai_memory

# 检查环境变量
echo $POSTGRES_PASSWORD
```

#### 3. 应用启动失败

**症状**: Flask应用无法启动

**解决方法**:
```bash
# 查看应用日志
docker-compose logs app

# 检查环境变量
docker-compose config | grep -A5 app

# 重启应用
docker-compose restart app

# 检查端口占用
sudo netstat -tlnp | grep :8000
```

#### 4. 内存不足

**症状**: 系统响应缓慢，容器频繁重启

**解决方法**:
```bash
# 查看内存使用
free -h
docker stats

# 优化PostgreSQL配置
# 编辑 docker-compose.prod.yml，减少 shared_buffers
# 重启服务
docker-compose down && docker-compose up -d
```

### 调试命令

```bash
# 进入容器调试
docker exec -it ai_memory_app bash
docker exec -it ai_memory_postgres bash
docker exec -it ai_memory_nginx bash

# 检查网络连接
docker network inspect ai_memory_experiment_app-network

# 检查服务发现
docker-compose exec app curl http://db:5432
```

## 备份与恢复

### 备份策略

1. **数据库备份**: 每日自动备份，保留7天
2. **配置文件**: Git版本控制
3. **SSL证书**: 自动续期
4. **应用数据**: 数据库备份 + 日志轮转

### 恢复流程

1. **数据库恢复**:
   ```bash
   # 停止应用
   docker-compose down

   # 恢复数据库
   gunzip -c backups/backup_20250101_120000.sql.gz | docker exec -i ai_memory_postgres psql -U ai_memory -d ai_memory

   # 启动服务
   docker-compose up -d
   ```

2. **完整恢复**:
   ```bash
   # 克隆项目
   git clone <repository-url>
   cd ai_memory_experiment

   # 恢复配置文件
   cp backup/env.production .env.production

   # 恢复数据库
   # ...（同上）

   # 启动服务
   docker-compose up -d
   ```

## 性能优化

### ECS优化

1. **系统参数优化**:
   ```bash
   # 编辑 /etc/sysctl.conf
   net.core.somaxconn=65535
   net.ipv4.tcp_max_syn_backlog=65535
   net.ipv4.ip_local_port_range=1024 65535
   vm.swappiness=10
   vm.overcommit_memory=1

   # 生效配置
   sudo sysctl -p
   ```

2. **Docker优化**:
   ```bash
   # 编辑 /etc/docker/daemon.json
   {
     "log-driver": "json-file",
     "log-opts": {
       "max-size": "10m",
       "max-file": "3"
     },
     "storage-driver": "overlay2",
     "live-restore": true
   }

   # 重启Docker
   sudo systemctl restart docker
   ```

### 应用优化

1. **调整waitress线程数**:
   ```bash
   # 编辑 .env.production
   WORKERS=4  # 根据CPU核心数调整
   ```

2. **数据库连接池**:
   ```bash
   # 编辑 docker-compose.prod.yml
   command: >
     postgres
     -c max_connections=200
     -c shared_buffers=256MB
     -c effective_cache_size=1GB
   ```

## 监控告警

### 阿里云监控

1. 配置云监控告警：
   - CPU使用率 > 80%
   - 内存使用率 > 85%
   - 磁盘使用率 > 90%

2. 配置日志服务：
   - 收集Nginx访问日志
   - 收集应用错误日志
   - 设置关键词告警（error, exception, failed）

### 自定义监控

```bash
# 创建定时监控任务
crontab -e

# 添加以下行（每小时检查）
0 * * * * /path/to/ai_memory_experiment/deploy/monitor.sh >> /var/log/ai-memory-monitor.log

# 每天备份数据库
0 2 * * * /path/to/ai_memory_experiment/deploy/backup-postgres.sh
```

## 联系方式

如遇问题，请查看：
1. 项目README.md
2. 日志文件：`logs/app.log`
3. Nginx日志：`nginx/logs/`

或联系项目维护者。

---

**最后更新**: 2026-04-05
**部署版本**: v1.0.0