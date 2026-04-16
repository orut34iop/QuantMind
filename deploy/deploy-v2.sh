#!/bin/bash
#===============================================================================
# QuantMind 一键部署脚本 (国内优化版 v3.0)
# 适用于 Ubuntu 20.04/22.04/24.04
# 
# 特性:
#   - 使用阿里云 Docker 镜像
#   - 使用淘宝 Node.js 镜像
#   - 使用淘宝 npm 镜像
#   - 支持断点续传
#
# 使用方式:
#   chmod +x deploy-v2.sh
#   sudo ./deploy-v2.sh
#===============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
DEPLOY_DIR="/opt/quantmind"
DATA_DIR="/opt/quantmind/data"
REPO_URL="https://gitee.com/qusong0627/quantmind.git"
NODE_VERSION="20.19.0"
DOCKER_MIRROR="https://naw1faud2gpqbs.xuanyuan.run"

# 自动获取服务器 IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

# 进度文件
PROGRESS_FILE="/tmp/quantmind_deploy_progress"

# 日志函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "\n${BLUE}========================================${NC}\n${BLUE}  $1${NC}\n${BLUE}========================================${NC}\n"; }
log_done() { echo -e "${GREEN}✅ $1 完成${NC}\n"; }

# 保存进度
save_progress() {
    echo "$1" > $PROGRESS_FILE
    log_info "进度已保存: Step $1"
}

# 读取进度
get_progress() {
    if [[ -f $PROGRESS_FILE ]]; then
        cat $PROGRESS_FILE
    else
        echo "0"
    fi
}

# 检查 root 权限
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要 root 权限运行"
        log_info "请使用: sudo ./deploy-v2.sh"
        exit 1
    fi
}

#===============================================================================
# Step 1: 更新系统
#===============================================================================
step1_update_system() {
    log_step "Step 1: 更新系统依赖"
    
    log_info "更新 apt 源..."
    apt-get update -y
    
    log_info "安装基础工具..."
    apt-get install -y \
        curl wget git vim htop net-tools \
        ca-certificates gnupg lsb-release \
        software-properties-common build-essential \
        libssl-dev libffi-dev python3-dev python3-pip python3-venv \
        openssl
    
    log_done "Step 1"
    save_progress "1"
}

#===============================================================================
# Step 2: 安装 Docker (阿里云镜像)
#===============================================================================
step2_install_docker() {
    log_step "Step 2: 安装 Docker (阿里云镜像)"
    
    if command -v docker &> /dev/null; then
        log_warn "Docker 已安装: $(docker --version)"
    else
        log_info "使用阿里云镜像安装 Docker..."
        curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
        
        # 启动 Docker
        systemctl start docker
        systemctl enable docker
        
        # 将用户加入 docker 组
        if [[ -n "$SUDO_USER" ]]; then
            usermod -aG docker $SUDO_USER
            log_info "已将用户 $SUDO_USER 加入 docker 组"
        fi
        
        log_info "Docker 安装完成: $(docker --version)"
    fi
    
    # 配置 Docker 镜像加速器
    log_info "配置 Docker 镜像加速器..."
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << EOF
{
    "registry-mirrors": [
        "${DOCKER_MIRROR}"
    ]
}
EOF
    systemctl daemon-reload
    systemctl restart docker
    sleep 3
    
    # 验证 Docker Compose
    if docker compose version &> /dev/null; then
        log_info "Docker Compose: $(docker compose version)"
    fi
    
    log_done "Step 2"
    save_progress "2"
}

#===============================================================================
# Step 3: 安装 Node.js (淘宝镜像)
#===============================================================================
step3_install_nodejs() {
    log_step "Step 3: 安装 Node.js (淘宝镜像)"
    
    if command -v node &> /dev/null && [[ "$(node --version)" == "v${NODE_VERSION}" ]]; then
        log_warn "Node.js 已安装: $(node --version)"
    else
        log_info "使用淘宝镜像安装 Node.js ${NODE_VERSION}..."
        
        # 清理旧版本
        apt-get remove -y nodejs 2>/dev/null || true
        
        # 下载 Node.js
        NODE_URL="https://npmmirror.com/mirrors/node/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz"
        log_info "下载: $NODE_URL"
        curl -fsSL $NODE_URL -o /tmp/node.tar.xz
        
        # 解压安装
        mkdir -p /usr/local/nodejs
        tar -xJf /tmp/node.tar.xz -C /usr/local/nodejs --strip-components=1
        
        # 创建软链接
        ln -sf /usr/local/nodejs/bin/node /usr/local/bin/node
        ln -sf /usr/local/nodejs/bin/npm /usr/local/bin/npm
        ln -sf /usr/local/nodejs/bin/npx /usr/local/bin/npx
        
        # 配置 npm 淘宝镜像
        npm config set registry https://registry.npmmirror.com
        
        log_info "Node.js 安装完成: $(node --version)"
        log_info "npm 版本: $(npm --version)"
        log_info "npm 镜像: $(npm config get registry)"
    fi
    
    log_done "Step 3"
    save_progress "3"
}

#===============================================================================
# Step 4: 安装 PM2
#===============================================================================
step4_install_pm2() {
    log_step "Step 4: 安装 PM2"
    
    if command -v pm2 &> /dev/null; then
        log_warn "PM2 已安装: $(pm2 --version)"
    else
        log_info "安装 PM2..."
        npm install -g pm2
        
        # 创建软链接
        ln -sf /usr/local/nodejs/bin/pm2 /usr/local/bin/pm2
        ln -sf /usr/local/nodejs/bin/pm2-dev /usr/local/bin/pm2-dev
        ln -sf /usr/local/nodejs/bin/pm2-docker /usr/local/bin/pm2-docker
        ln -sf /usr/local/nodejs/bin/pm2-runtime /usr/local/bin/pm2-runtime
        
        log_info "PM2 安装完成: $(pm2 --version)"
    fi
    
    log_done "Step 4"
    save_progress "4"
}

#===============================================================================
# Step 5: 安装 Nginx
#===============================================================================
step5_install_nginx() {
    log_step "Step 5: 安装 Nginx"
    
    if command -v nginx &> /dev/null; then
        log_warn "Nginx 已安装: $(nginx -v 2>&1)"
    else
        log_info "安装 Nginx..."
        apt-get install -y nginx
        
        # 备份默认配置
        cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak
        
        log_info "Nginx 安装完成: $(nginx -v 2>&1)"
    fi
    
    log_done "Step 5"
    save_progress "5"
}

#===============================================================================
# Step 6: 克隆代码
#===============================================================================
step6_clone_code() {
    log_step "Step 6: 克隆代码 (Gitee)"
    
    mkdir -p $DEPLOY_DIR
    
    if [[ -d "$DEPLOY_DIR/quantmind" ]]; then
        log_warn "代码目录已存在，执行更新..."
        cd $DEPLOY_DIR/quantmind
        git pull origin master
    else
        log_info "从 Gitee 克隆代码..."
        cd $DEPLOY_DIR
        git clone $REPO_URL quantmind
        cd quantmind
    fi
    
    # 修复权限
    chown -R ${SUDO_USER:-root}:${SUDO_USER:-root} $DEPLOY_DIR/quantmind
    
    log_info "代码目录: $(pwd)"
    log_info "当前分支: $(git branch --show-current)"
    log_info "最新提交: $(git log -1 --oneline)"
    
    log_done "Step 6"
    save_progress "6"
}

#===============================================================================
# Step 7: 配置环境变量
#===============================================================================
step7_config_environment() {
    log_step "Step 7: 配置环境变量"
    
    cd $DEPLOY_DIR/quantmind
    
    if [[ -f ".env" ]]; then
        log_warn ".env 文件已存在，跳过创建"
    else
        log_info "创建 .env 配置文件..."
        
        # 生成随机密钥
        SECRET_KEY=$(openssl rand -hex 32)
        JWT_SECRET_KEY=$(openssl rand -hex 32)
        
        cat > .env << EOF
# QuantMind OSS Edition 配置

APP_EDITION=oss
APP_ENV=production
TZ=Asia/Shanghai

SECRET_KEY=${SECRET_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}

DB_HOST=db
DB_PORT=5432
DB_NAME=quantmind
DB_USER=quantmind
DB_PASSWORD=quantmind2026

REDIS_HOST=redis
REDIS_PORT=6379

STORAGE_MODE=local
STORAGE_ROOT=${DATA_DIR}

# 前端使用相对路径，通过 Nginx 代理访问后端
# 不需要配置 VITE_API_URL

DEBUG=false
LOG_LEVEL=INFO
EOF
        
        log_info ".env 文件创建完成"
    fi
    
    # 创建数据目录
    mkdir -p $DATA_DIR/{postgres,redis,logs,models,qlib_data}
    log_info "数据目录创建完成: $DATA_DIR"
    
    log_done "Step 7"
    save_progress "7"
}

#===============================================================================
# Step 8: 构建 Docker 镜像
#===============================================================================
step8_build_docker() {
    log_step "Step 8: 构建 Docker 镜像"
    
    cd $DEPLOY_DIR/quantmind
    
    log_info "构建 QuantMind OSS 镜像 (可能需要 5-10 分钟)..."
    docker build -t quantmind-oss:latest -f docker/Dockerfile.oss .
    
    log_info "镜像构建完成:"
    docker images | grep quantmind-oss
    
    log_done "Step 8"
    save_progress "8"
}

#===============================================================================
# Step 9: 启动后端服务
#===============================================================================
step9_start_backend() {
    log_step "Step 9: 启动后端服务"
    
    cd $DEPLOY_DIR/quantmind
    
    log_info "启动 Docker Compose 服务..."
    docker compose up -d
    
    log_info "等待服务启动 (30秒)..."
    sleep 30
    
    log_info "检查服务状态:"
    docker compose ps
    
    log_done "Step 9"
    save_progress "9"
}

#===============================================================================
# Step 10: 初始化数据库
#===============================================================================
step10_init_database() {
    log_step "Step 10: 初始化数据库"
    
    cd $DEPLOY_DIR/quantmind
    
    # 等待数据库就绪
    log_info "等待数据库完全就绪..."
    sleep 10
    
    if [[ -f "data/quantmind_init.sql" ]]; then
        log_info "初始化数据库..."
        docker exec -i quantmind-db psql -U quantmind -d quantmind < data/quantmind_init.sql 2>&1 | head -20 || \
            log_warn "数据库可能已初始化"
        log_info "数据库初始化完成"
    else
        log_warn "未找到数据库初始化 SQL 文件: data/quantmind_init.sql"
    fi
    
    log_done "Step 10"
    save_progress "10"
}

#===============================================================================
# Step 11: 安装前端依赖
#===============================================================================
step11_install_frontend() {
    log_step "Step 11: 安装前端依赖"
    
    cd $DEPLOY_DIR/quantmind
    
    # 修复权限
    chown -R ${SUDO_USER:-root}:${SUDO_USER:-root} .
    
    log_info "安装 npm 依赖 (可能需要 3-5 分钟)..."
    sudo -u ${SUDO_USER:-root} npm install
    
    log_done "Step 11"
    save_progress "11"
}

#===============================================================================
# Step 12: 构建前端
#===============================================================================
step12_build_frontend() {
    log_step "Step 12: 构建前端"
    
    cd $DEPLOY_DIR/quantmind
    
    log_info "构建生产版本 (可能需要 2-3 分钟)..."
    sudo -u ${SUDO_USER:-root} npm run dashboard:build
    
    log_info "前端构建完成"
    ls -la electron/dist-react/ | head -10
    
    log_done "Step 12"
    save_progress "12"
}

#===============================================================================
# Step 13: 启动前端服务
#===============================================================================
step13_start_frontend() {
    log_step "Step 13: 启动前端服务 (PM2)"
    
    cd $DEPLOY_DIR/quantmind
    
    log_info "停止旧服务..."
    pm2 delete quantmind-web 2>/dev/null || true
    
    log_info "启动新服务..."
    pm2 start npm --name "quantmind-web" -- run dashboard:preview
    
    log_info "保存 PM2 配置..."
    pm2 save
    
    # 设置开机自启
    log_info "设置开机自启..."
    pm2 startup systemd -u ${SUDO_USER:-root} --hp /home/${SUDO_USER:-root} 2>/dev/null || true
    
    log_info "PM2 服务状态:"
    pm2 status
    
    log_done "Step 13"
    save_progress "13"
}

#===============================================================================
# Step 14: 配置 Nginx
#===============================================================================
step14_config_nginx() {
    log_step "Step 14: 配置 Nginx"
    
    log_info "创建 Nginx 配置..."
    cat > /etc/nginx/sites-available/quantmind << 'EOF'
server {
    listen 80;
    server_name _;
    
    client_max_body_size 100M;
    
    # 前端
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
    
    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    # WebSocket
    location /ws/ {
        proxy_pass http://127.0.0.1:8003/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
    
    # Engine API
    location /engine/ {
        proxy_pass http://127.0.0.1:8001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
    
    # Trade API
    location /trade/ {
        proxy_pass http://127.0.0.1:8002/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
    
    # 启用配置
    ln -sf /etc/nginx/sites-available/quantmind /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # 测试配置
    log_info "测试 Nginx 配置..."
    nginx -t
    
    # 重启 Nginx
    log_info "重启 Nginx..."
    systemctl restart nginx
    systemctl enable nginx
    
    log_info "Nginx 状态:"
    systemctl status nginx --no-pager | head -10
    
    log_done "Step 14"
    save_progress "14"
}

#===============================================================================
# Step 15: 健康检查
#===============================================================================
step15_health_check() {
    log_step "Step 15: 健康检查"
    
    log_info "Docker 容器状态:"
    docker compose -f $DEPLOY_DIR/quantmind/docker-compose.yml ps
    
    echo ""
    log_info "PM2 服务状态:"
    pm2 status
    
    echo ""
    log_info "端口监听:"
    ss -tlnp | grep -E ':(80|3000|8000|8001|8002|8003|5432|6379)' || netstat -tlnp | grep -E ':(80|3000|8000|8001|8002|8003|5432|6379)'
    
    echo ""
    log_info "测试后端 API..."
    curl -s http://localhost:8000/health -o /dev/null && log_info "后端 API: 正常" || log_warn "后端 API: 未就绪"
    
    echo ""
    log_info "测试前端..."
    curl -s http://localhost:3000 -o /dev/null && log_info "前端服务: 正常" || log_warn "前端服务: 未就绪"
    
    echo ""
    log_info "测试 Nginx..."
    curl -s http://localhost -o /dev/null && log_info "Nginx: 正常" || log_warn "Nginx: 未就绪"
    
    log_done "Step 15"
    save_progress "15"
}

#===============================================================================
# Step 16: 配置防火墙
#===============================================================================
step16_firewall() {
    log_step "Step 16: 配置防火墙"
    
    if command -v ufw &> /dev/null; then
        log_info "配置 UFW 防火墙..."
        
        ufw allow 22/tcp comment 'SSH'
        ufw allow 80/tcp comment 'HTTP'
        ufw allow 443/tcp comment 'HTTPS'
        ufw allow 3000/tcp comment 'Frontend'
        
        ufw --force enable
        
        ufw status
    else
        log_warn "UFW 未安装，跳过防火墙配置"
    fi
    
    log_done "Step 16"
    save_progress "16"
}

#===============================================================================
# 完成
#===============================================================================
show_info() {
    log_step "🎉 部署完成"
    
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  QuantMind 部署成功！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "访问地址:"
    echo -e "  前端: ${BLUE}http://${SERVER_IP}${NC}"
    echo -e "  后端: ${BLUE}http://${SERVER_IP}:8000/docs${NC}"
    echo -e "  Engine: ${BLUE}http://${SERVER_IP}:8001/docs${NC}"
    echo ""
    echo -e "默认管理员账号:"
    echo -e "  用户名: ${YELLOW}admin${NC}"
    echo -e "  密码:   ${YELLOW}需要通过 API 重置${NC}"
    echo ""
    echo -e "常用命令:"
    echo -e "  查看后端日志: docker compose -f $DEPLOY_DIR/quantmind/docker-compose.yml logs -f"
    echo -e "  查看前端日志: pm2 logs quantmind-web"
    echo -e "  重启后端:     docker compose -f $DEPLOY_DIR/quantmind/docker-compose.yml restart"
    echo -e "  重启前端:     pm2 restart quantmind-web"
    echo -e "  重启 Nginx:   systemctl restart nginx"
    echo ""
    echo -e "部署目录: $DEPLOY_DIR/quantmind"
    echo -e "数据目录: $DATA_DIR"
    echo ""
}

#===============================================================================
# 主函数
#===============================================================================
main() {
    clear
    
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  QuantMind 一键部署脚本${NC}"
    echo -e "${GREEN}  版本: 3.0.0 (国内优化版)${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    check_root
    
    # 获取当前进度
    CURRENT_STEP=$(get_progress)
    if [[ "$CURRENT_STEP" != "0" ]]; then
        log_info "检测到上次部署进度: Step $CURRENT_STEP"
        log_info "将从 Step $((CURRENT_STEP + 1)) 继续部署"
        echo ""
    fi
    
    # 执行部署步骤
    [[ $CURRENT_STEP -lt 1 ]] && step1_update_system
    [[ $CURRENT_STEP -lt 2 ]] && step2_install_docker
    [[ $CURRENT_STEP -lt 3 ]] && step3_install_nodejs
    [[ $CURRENT_STEP -lt 4 ]] && step4_install_pm2
    [[ $CURRENT_STEP -lt 5 ]] && step5_install_nginx
    [[ $CURRENT_STEP -lt 6 ]] && step6_clone_code
    [[ $CURRENT_STEP -lt 7 ]] && step7_config_environment
    [[ $CURRENT_STEP -lt 8 ]] && step8_build_docker
    [[ $CURRENT_STEP -lt 9 ]] && step9_start_backend
    [[ $CURRENT_STEP -lt 10 ]] && step10_init_database
    [[ $CURRENT_STEP -lt 11 ]] && step11_install_frontend
    [[ $CURRENT_STEP -lt 12 ]] && step12_build_frontend
    [[ $CURRENT_STEP -lt 13 ]] && step13_start_frontend
    [[ $CURRENT_STEP -lt 14 ]] && step14_config_nginx
    [[ $CURRENT_STEP -lt 15 ]] && step15_health_check
    [[ $CURRENT_STEP -lt 16 ]] && step16_firewall
    
    show_info
    
    # 清理进度文件
    rm -f $PROGRESS_FILE
}

# 执行主函数
main "$@"
