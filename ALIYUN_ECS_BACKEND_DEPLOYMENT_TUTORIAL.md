# 阿里云 ECS 后端部署教学记录

这个文件用于记录 `vita-company` 后端部署到阿里云 ECS 的分步教学。

使用方式：

1. 你每完成当前任务，就告诉我完成情况和遇到的问题。
2. 我会在本文件末尾追加下一步教学，不覆盖前面的内容。
3. 不要把真实的 API Key、JWT 密钥、服务器密码写进聊天或提交到 Git。

当前目标：先部署一个可投简历展示的后端 demo。

技术路线：

- 云服务器：阿里云 ECS
- 系统：Ubuntu 22.04 LTS 或 Ubuntu 24.04 LTS
- 后端：FastAPI + Uvicorn
- 进程管理：systemd
- Web 入口：Nginx 反向代理
- 数据库：先用 SQLite，后续再考虑 PostgreSQL

## 进度

- [ ] 领取或购买阿里云 ECS
- [ ] 配置安全组
- [ ] SSH 连接服务器
- [ ] 安装服务器基础环境
- [ ] 上传或拉取项目代码
- [ ] 配置后端 `.env`
- [ ] 安装 Python 依赖并运行 Alembic
- [ ] 配置 systemd 后台服务
- [ ] 配置 Nginx 反向代理
- [ ] 验收线上接口

## 第 1 步：领取或购买阿里云 ECS

先完成服务器创建，不急着上传代码。

建议配置：

- 地域：离你或目标用户近即可，例如华东、华北、华南。
- 镜像：优先 `Ubuntu 24.04 LTS`，没有就选 `Ubuntu 22.04 LTS`。
- 规格：优先 `2核2G`；如果免费额度只有 `1核1G`，也可以先用来做 demo。
- 登录方式：建议先用密码登录，后续再升级成 SSH 密钥。
- 公网 IP：必须开启，否则外部访问不到。
- 带宽：1 Mbps 也能演示 Swagger 和普通接口；如果要频繁传 PDF，带宽越高越舒服。

创建完成后，你需要记录这几项：

```text
公网 IP：
系统版本：
登录用户名：root 或 ecs-user
是否能在控制台看到实例运行中：
```

注意：

- 不要把服务器登录密码发给我。
- 如果阿里云提示试用到期时间，自己记到日历里，避免自动扣费。
- 如果暂时没有域名，先用公网 IP 部署即可。

完成后告诉我：

```text
第 1 步完成：
公网 IP 已拿到
系统是 Ubuntu xx.xx
实例状态是运行中
```

## 当前续接点（基于 2026-04-24 已完成状态）

上一次已经完成的实际状态不是“刚买服务器”，而是已经把后端临时跑起来了。

当前线上已确认状态：

- 云厂商：阿里云 ECS
- 地域：杭州
- 系统：Ubuntu 22.04
- 机器规格：2 vCPU / 2 GiB / 40 GiB / 3 Mbps
- 项目路径：`/srv/vita-company/backend`
- 当前运行方式：`nohup` 临时启动
- 当前端口：`8000`
- 已验证接口：
  - `GET /api/v1/health`
  - `GET /api/v1/health/db`
  - `/docs`

这意味着前 1 到 7 步已经完成到“能跑通后端”的程度，当前真正该做的是把临时进程切换成正式托管服务。

当前剩余目标：

- [ ] 配置 systemd 后台服务
- [ ] 配置 Nginx 反向代理
- [ ] 验收线上接口并收口安全组

## 第 8 步：配置 systemd 后台服务

这一小步的目标很单纯：

1. 停掉现在的 `nohup` 临时进程。
2. 改成由 `systemd` 托管。
3. 保证服务器重启后后端能自动拉起。

先登录服务器：

```bash
ssh root@你的公网IP
```

### 8.1 确认当前临时进程

先看当前 `uvicorn` 进程和 8000 端口占用：

```bash
ps -ef | grep uvicorn | grep -v grep
sudo ss -lntp | grep 8000
```

你应该能看到当前 `nohup` 跑起来的 `uvicorn`。

### 8.2 写入 systemd 服务文件

执行下面命令，创建服务：

```bash
sudo tee /etc/systemd/system/vita-backend.service > /dev/null <<'EOF'
[Unit]
Description=Vita Company FastAPI Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/srv/vita-company/backend
ExecStart=/srv/vita-company/backend/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
```

说明：

- 这里先继续监听 `0.0.0.0:8000`，因为 Nginx 还没上。
- 等下一步 Nginx 配好后，再把监听改成 `127.0.0.1:8000`，同时关闭安全组里的 `8000`。
- 应用会优先读取 `/srv/vita-company/backend/.env`，如果那里没有，再读项目根目录 `.env`。生产环境建议把真正的配置放在 `backend/.env`。

### 8.3 停掉旧进程，启动 systemd

如果上一步 `ps -ef` 看到了旧的 `uvicorn` PID，用下面命令停掉它：

```bash
sudo kill 旧进程PID
```

然后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable vita-backend
sudo systemctl start vita-backend
sudo systemctl status vita-backend --no-pager
```

如果状态不是 `active (running)`，马上查看日志：

```bash
sudo journalctl -u vita-backend -n 100 --no-pager
```

### 8.4 做本机验收

在服务器上执行：

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/health/db
```

预期：

- 两个接口都返回成功 JSON。
- `sudo systemctl status vita-backend --no-pager` 显示 `active (running)`。

### 8.5 这一阶段先不要做的事

暂时先不要做下面这些动作，等第 9 步再一起收口：

- 不要先关闭安全组 `8000`
- 不要先把 `uvicorn` 监听地址改成 `127.0.0.1`
- 不要先折腾 HTTPS

### 第 8 步完成后，告诉我

把下面这段填好发给我：

```text
第 8 步完成：
systemd 服务名是 vita-backend
systemctl 状态是 active (running) / 不是
127.0.0.1:8000/api/v1/health 是否正常
127.0.0.1:8000/api/v1/health/db 是否正常
如果失败，把 journalctl 最后 30 行报错贴给我
```

## 第 9 步：配置 Nginx 反向代理

第 8 步通过后，下一步是把公网入口从“直接暴露 `8000`”改成“公网走 `80`，内部转发到 `8000`”。

这一小步的目标：

1. 安装 Nginx。
2. 让公网访问 `http://你的IP/` 时转发到后端。
3. 保留 `/docs`、`/api/v1/*`、WebSocket 的可用性。

### 9.1 安装 Nginx

```bash
sudo apt update
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl status nginx --no-pager
```

### 9.2 写入站点配置

先删除默认站点，避免和新配置冲突：

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-available/default
```

然后写入 `vita-backend` 配置：

```bash
sudo tee /etc/nginx/sites-available/vita-backend > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name _;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
EOF
```

启用配置并校验：

```bash
sudo ln -sf /etc/nginx/sites-available/vita-backend /etc/nginx/sites-enabled/vita-backend
sudo nginx -t
sudo systemctl reload nginx
```

### 9.3 本机验收

先在服务器本机验证：

```bash
curl http://127.0.0.1/api/v1/health
curl http://127.0.0.1/api/v1/health/db
curl -I http://127.0.0.1/docs
```

预期：

- `/api/v1/health` 返回成功 JSON
- `/api/v1/health/db` 返回成功 JSON
- `/docs` 返回 `200 OK`

### 9.4 公网验收

再在你本地电脑浏览器里打开：

```text
http://你的公网IP/docs
http://你的公网IP/api/v1/health
```

如果你习惯命令行，也可以在服务器上直接测试 Host 入口：

```bash
curl http://你的公网IP/api/v1/health
```

### 9.5 第 9 步先不要做的事

先不要急着改下面两项，等确认 Nginx 入口稳定后再收口：

- 暂时不要关安全组 `8000`
- 暂时不要把 `uvicorn` 的监听改成 `127.0.0.1:8000`

因为现在的目标只是先确认 Nginx 代理链路可用。

### 第 9 步完成后，告诉我

把下面这段填好发给我：

```text
第 9 步完成：
nginx 状态是否 active (running)
nginx -t 是否 successful
http://127.0.0.1/api/v1/health 是否正常
http://公网IP/api/v1/health 是否正常
http://公网IP/docs 是否正常
如果失败，把 sudo nginx -t 和 sudo journalctl -u nginx -n 30 --no-pager 贴给我
```

## 第 10 步：收口安全组与内部监听

第 9 步通过后，公网入口已经从 `8000` 切到了 `80`。现在该把临时暴露的 `8000` 收回去。

这一小步的目标：

1. 把 `uvicorn` 从 `0.0.0.0:8000` 改成只监听 `127.0.0.1:8000`
2. 保证 `Nginx -> 127.0.0.1:8000` 仍然正常
3. 去阿里云安全组里删除公网 `8000` 入站规则

### 10.1 修改 systemd 服务监听地址

先直接编辑服务文件：

```bash
sudo sed -i 's/--host 0.0.0.0/--host 127.0.0.1/' /etc/systemd/system/vita-backend.service
sudo cat /etc/systemd/system/vita-backend.service
```

你应该看到这一行变成：

```text
ExecStart=/srv/vita-company/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 10.2 重载并重启后端服务

```bash
sudo systemctl daemon-reload
sudo systemctl restart vita-backend
sudo systemctl status vita-backend --no-pager
sudo ss -lntp | grep 8000
```

预期：

- `vita-backend` 仍然是 `active (running)`
- `8000` 只监听在 `127.0.0.1:8000`

### 10.3 本机与公网验收

在服务器上执行：

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1/api/v1/health
curl http://127.0.0.1/api/v1/health/db
```

然后在你本地电脑浏览器里再验证：

```text
http://8.136.145.232/docs
http://8.136.145.232/api/v1/health
```

预期：

- 本机直连 `127.0.0.1:8000` 正常
- 通过 `Nginx` 的 `127.0.0.1` 正常
- 公网 `8.136.145.232` 正常

### 10.4 删除阿里云安全组中的 8000 端口

这一步去阿里云控制台操作，不是在 SSH 里做。

进入：

```text
ECS 控制台 -> 实例 -> 安全组 -> 入方向规则
```

把临时开放的：

```text
TCP 8000/8000 0.0.0.0/0
```

删除。

保留：

- `22`：SSH
- `80`：HTTP

如果你暂时不做 HTTPS，`443` 可以先不开。

### 10.5 可选的进一步收口

如果你登录服务器的来源 IP 比较固定，建议顺手把 `22` 改成只允许你的公网 IP，而不是 `0.0.0.0/0`。

### 第 10 步完成后，告诉我

把下面这段填好发给我：

```text
第 10 步完成：
vita-backend 是否 active (running)
8000 是否只监听 127.0.0.1
http://127.0.0.1/api/v1/health 是否正常
http://8.136.145.232/api/v1/health 是否正常
安全组 8000 是否已删除
```

## 当前已完成状态（截至 2026-04-25）

当前线上部署已经达到这个状态：

- `systemd` 托管后端服务：`vita-backend`
- `Nginx` 作为公网入口监听 `80`
- `uvicorn` 只监听 `127.0.0.1:8000`
- 阿里云安全组已删除公网 `8000` 入站规则
- 当前公网可访问地址：
  - `http://8.136.145.232/api/v1/health`
  - `http://8.136.145.232/docs`

现在的真实链路是：

```text
Browser / APK
  -> http://8.136.145.232:80
  -> Nginx
  -> 127.0.0.1:8000
  -> FastAPI
```

## 第 11 步：域名与 HTTPS（下一步优先推荐）

如果后面是浏览器访问，HTTP 还能临时演示。

但如果你的 APK 要直接调用这个后端，强烈建议尽快上 `HTTPS`，因为很多 Android 环境默认不允许明文 HTTP 请求，除非你额外配置 cleartext 例外。

这一小步的目标：

1. 准备一个域名，例如 `api.xxx.com`
2. 把域名解析到 `8.136.145.232`
3. 用 Nginx + Let's Encrypt 配置 HTTPS

开始前你需要准备：

- 一个你可控的域名
- 一个二级域名，例如 `api.yourdomain.com`
- DNS A 记录指向：`8.136.145.232`

如果你还没有域名，就先停在当前状态也可以，当前后端已经能用于基础演示和联调。

等你准备好域名后，我会继续带你做：

1. DNS 解析检查
2. Nginx `server_name` 改成正式域名
3. `certbot` 申请证书
4. 自动续期验证
5. 最终把 API 基地址切换成 `https://你的域名/api/v1`

## 第 11 步（简历亮点优先版）：把后端切到 Docker

如果你的当前目标是“尽快让简历更像工程化项目”，那 Docker 比域名和 HTTPS 更值得先做。

这一小步的目标：

1. 保留现有 `Nginx -> 127.0.0.1:8000 -> FastAPI` 链路不变
2. 把 `uvicorn` 的运行方式从宿主机 Python 进程切成 Docker 容器
3. 保证 SQLite 数据和 `storage` 目录仍然持久化

仓库里已经补好的 Docker 资产：

- `docker-compose.yml`
- `backend/Dockerfile`
- `backend/.dockerignore`
- `backend/scripts/docker-entrypoint.sh`

### 11.1 Docker 方案说明

当前 Docker 方案是：

```text
Nginx (host, port 80)
  -> 127.0.0.1:8000 on host
  -> Docker container port 8000
  -> FastAPI
```

数据持久化策略：

- 宿主机 `./backend/healthy_system.db` 挂载到容器 `/app/healthy_system.db`
- 宿主机 `./backend/storage` 挂载到容器 `/app/storage`

这样做的好处是切换最快，不会丢你现在 ECS 上已经存在的数据。

补充说明：

- `backend/Dockerfile` 现在支持通过构建参数 `PYTHON_BASE_IMAGE` 覆盖基础镜像
- 在国内网络环境下，如果直接访问 Docker Hub 超时，可以把它指向国内镜像前缀
- 容器内 `apt` 现在也建议改走阿里云 Debian 源，否则可能卡在 `apt-get install build-essential`

### 11.2 服务器安装 Docker

在 ECS 上执行：

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
docker --version
docker compose version
```

### 11.3 先停掉旧的宿主机 uvicorn

不要一开始就停旧服务。正确顺序是：

1. 先把 Docker 安装好
2. 先把镜像 build 成功
3. 再停旧服务
4. 再启动容器

如果你已经像这次一样停掉了旧服务，但 Docker 还没装成功，先立即恢复：

```bash
sudo systemctl enable vita-backend
sudo systemctl start vita-backend
sudo systemctl status vita-backend --no-pager
curl http://127.0.0.1/api/v1/health
curl http://8.136.145.232/api/v1/health
```

等 Docker `build` 成功之后，再执行：

```bash
sudo systemctl stop vita-backend
sudo systemctl disable vita-backend
sudo ss -lntp | grep 8000
```

预期：

- `8000` 不再被旧的宿主机 Python 进程占用

### 11.4 用 Docker Compose 启动

进入项目根目录：

```bash
cd /srv/vita-company
docker compose build
sudo systemctl stop vita-backend
sudo systemctl disable vita-backend
docker compose up -d
docker compose ps
docker compose logs --tail=100 backend
```

说明：

- `docker-compose.yml` 当前读取项目根目录 `./.env`
- 容器启动时会自动执行 `alembic upgrade head`
- 然后再启动 `uvicorn`
- 宿主机 Nginx 配置不需要改
- 如果 `docker compose build` 失败，不要停掉旧的 `vita-backend`

如果服务器拉取 Docker Hub 很慢或超时，可以先在项目根目录 `.env` 里追加：

```bash
echo 'PYTHON_BASE_IMAGE=m.daocloud.io/docker.io/library/python:3.13-slim' | sudo tee -a /srv/vita-company/.env
```

然后重新构建：

```bash
cd /srv/vita-company
docker compose build
```

这里使用的是 DaoCloud 的公开镜像加速前缀方案。DaoCloud 文档给出的规则是：

```text
原镜像：docker.io/library/python:3.13-slim
加速后：m.daocloud.io/docker.io/library/python:3.13-slim
```

如果 `docker compose build` 长时间卡在：

```text
apt-get update
apt-get install -y --no-install-recommends build-essential
```

说明不是业务代码问题，而是容器里的 Debian 包源下载慢。此时不要先停掉 `vita-backend`，应先把 `backend/Dockerfile` 里的 `apt` 源切到阿里云镜像后再重新 `build`。

### 11.5 验收

先在服务器本机执行：

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1/api/v1/health/db
curl http://127.0.0.1/api/v1/health
```

再在你本地电脑打开：

```text
http://8.136.145.232/api/v1/health
http://8.136.145.232/docs
```

如果容器正常，`docker compose ps` 里 `backend` 应该是 `running` 或 `healthy`。

### 11.6 常用运维命令

```bash
cd /srv/vita-company
docker compose up -d --build
docker compose down
docker compose restart
docker compose logs -f backend
docker compose ps
```

### 11.7 第 11 步完成后，告诉我

把下面这段填好发给我：

```text
第 11 步完成：
docker --version 是否正常
docker compose version 是否正常
docker compose ps 是否看到 backend running/healthy
http://127.0.0.1:8000/api/v1/health 是否正常
http://8.136.145.232/api/v1/health 是否正常
```

## 当前已完成状态（截至 2026-04-25 Docker 切换后）

当前线上后端已经切换为 Docker 运行，且验收通过：

- 宿主机 `docker` 与 `docker compose` 可用
- `docker compose build --no-cache` 成功
- `docker compose up -d` 成功
- 容器名：`vita-backend`
- 容器端口映射：`127.0.0.1:8000 -> 8000`
- 宿主机 `Nginx` 继续作为公网入口
- 宿主机旧 `systemd` 服务 `vita-backend` 已停止并禁用
- 当前验收通过：
  - `http://127.0.0.1:8000/api/v1/health`
  - `http://127.0.0.1:8000/api/v1/health/db`
  - `http://127.0.0.1/api/v1/health`
  - `http://8.136.145.232/api/v1/health`

当前真实链路：

```text
Browser / APK
  -> http://8.136.145.232:80
  -> Nginx
  -> 127.0.0.1:8000 on host
  -> Docker container vita-backend
  -> FastAPI
```

这一步完成后，你已经拥有一个更适合写进简历的部署结果：

- 阿里云 ECS
- Nginx 反向代理
- Docker Compose 容器化部署
- SQLite / storage 宿主机持久化
- Alembic 启动迁移
- 服务公网可访问

## 第 12 步：补基础备份与常用运维命令

现在你的服务已经能稳定跑了。下一步不依赖域名，优先做基础运维收尾。

这一小步的目标：

1. 给 SQLite 和 `storage` 做基础备份
2. 留一套你以后自己维护时常用的 Docker 运维命令
3. 让这套部署更像“可长期维护”的工程，而不是一次性演示

仓库里已经补好的脚本：

- `backend/scripts/backup_runtime_data.sh`

这个脚本会做两件事：

- 用 Python 标准库 `sqlite3.backup()` 备份正在使用中的 `healthy_system.db`
- 打包 `backend/storage`（自动排除 `storage/backups`，避免无限套娃）

### 12.1 先在服务器上试跑一次备份

```bash
cd /srv/vita-company
chmod +x backend/scripts/backup_runtime_data.sh
./backend/scripts/backup_runtime_data.sh
ls -lah backend/storage/backups
```

如果成功，你会看到类似：

```text
backend/storage/backups/20260425_170000/
```

这个目录下面通常有：

- `healthy_system.db`
- `storage.tar.gz`
- `manifest.txt`

### 12.2 建一个每天定时备份

直接用 root 的 crontab：

```bash
(crontab -l 2>/dev/null; echo '15 3 * * * cd /srv/vita-company && /srv/vita-company/backend/scripts/backup_runtime_data.sh >> /var/log/vita-backup.log 2>&1') | crontab -
crontab -l
```

这条规则的含义：

- 每天凌晨 `03:15`
- 执行一次后端运行时数据备份
- 日志追加到 `/var/log/vita-backup.log`

### 12.3 当前常用 Docker 运维命令

后面你维护这个项目，最常用的就是这些：

```bash
cd /srv/vita-company
docker compose ps
docker compose logs -f backend
docker compose restart backend
docker compose up -d --build
docker compose down
docker image prune -f
```

### 12.4 第 12 步完成后，告诉我

把下面这段填好发给我：

```text
第 12 步完成：
备份脚本是否执行成功
backend/storage/backups 下是否看到时间戳目录
crontab 是否已写入
docker compose ps 是否正常
```

## 第 13 步：域名与 HTTPS

截至 `2026-04-27`，这一步已经具备继续推进的前置条件：

- ICP 备案号：`鄂ICP备2026020960号-1`
- ECS 公网 IP：`8.136.145.232`
- 域名：`jibao.tech`
- `www.jibao.tech`
- DNS A 记录已指向：`8.136.145.232`
- 外部已验证：
  - `http://jibao.tech/api/v1/health`
  - `http://www.jibao.tech/api/v1/health`

当前欠缺的只是：

- 安全组放行 `443`
- Nginx 改为正式域名 `server_name`
- 用 `certbot` 签发证书

这一小步的目标：

1. 让 `https://jibao.tech` 可访问
2. 让 `https://www.jibao.tech` 可访问
3. 把 HTTP 自动跳转到 HTTPS
4. 保留当前 `Nginx -> 127.0.0.1:8000 -> Docker backend` 链路不变

### 13.1 先放行阿里云安全组 443

这一步在阿里云控制台操作，不是在 SSH 里做。

进入：

```text
ECS 控制台 -> 实例 -> 安全组 -> 入方向规则
```

确认至少保留：

- `22`：SSH
- `80`：HTTP
- `443`：HTTPS

如果 `443` 还没开，新增一条：

```text
TCP 443/443 0.0.0.0/0
```

### 13.2 登录服务器并确认当前站点配置

```bash
ssh root@8.136.145.232
sudo cat /etc/nginx/sites-available/vita-backend
```

如果你看到的还是之前的：

```text
server_name _;
```

就按下一步改成正式域名。

### 13.3 把 Nginx 改成正式域名入口

直接覆盖当前站点配置：

```bash
sudo tee /etc/nginx/sites-available/vita-backend > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name jibao.tech www.jibao.tech;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
EOF
```

然后校验并重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 13.4 安装 Certbot

在 Ubuntu 22.04 上直接安装：

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
certbot --version
```

### 13.5 申请 HTTPS 证书

执行：

```bash
sudo certbot --nginx -d jibao.tech -d www.jibao.tech
```

执行过程中：

- 邮箱填你常用邮箱
- Terms of Service 选同意
- 是否接收 EFF 邮件可选 `N`
- 当它问你是否把 HTTP 重定向到 HTTPS 时，选 `2: Redirect`

如果成功，`certbot` 会自动：

- 申请 Let’s Encrypt 证书
- 改写 Nginx HTTPS 配置
- 自动加 80 -> 443 跳转
- reload Nginx

### 13.6 验收 HTTPS

先在服务器本机执行：

```bash
curl -I https://jibao.tech
curl https://jibao.tech/api/v1/health
curl -I https://www.jibao.tech/docs
sudo nginx -t
```

再在你本地电脑浏览器打开：

```text
https://jibao.tech/docs
https://jibao.tech/api/v1/health
https://www.jibao.tech/docs
```

预期：

- 浏览器地址栏是锁
- `/api/v1/health` 返回成功 JSON
- `/docs` 正常打开
- 打开 `http://jibao.tech/docs` 会自动跳到 `https://jibao.tech/docs`

### 13.7 验证自动续期

```bash
sudo certbot renew --dry-run
```

如果成功，说明续期链路正常。

### 13.8 这一步完成后，前端与 APK 应该切换的地址

完成 HTTPS 后，临时公网 IP 接口地址就不再是首选了。

建议统一切到：

```text
https://jibao.tech/api/v1
```

Swagger：

```text
https://jibao.tech/docs
```

### 13.9 公安备案放在这一步之后做

当前更推荐的顺序是：

1. ICP 备案通过
2. 域名解析到 ECS
3. HTTPS 配好并稳定可访问
4. 再提交公安联网备案

这样公安备案页面里“网站访问地址”可以直接填最终地址，例如：

```text
https://jibao.tech/docs
```

补充说明：

- 公安备案里要求的“域名证书”通常是域名注册证书/域名所有权证明，不是 SSL 证书文件
- 如果后面公安审核人员直接打开首页，而你的 `/` 返回 `404`，通过率可能不如有首页时高；如有需要，可后续给 `/` 增加一个简单展示页

### 13.10 第 13 步完成后，告诉我

把下面这段填好发给我：

```text
第 13 步完成：
443 是否已放行
sudo certbot --nginx 是否成功
https://jibao.tech/api/v1/health 是否正常
https://www.jibao.tech/docs 是否正常
sudo certbot renew --dry-run 是否成功
如果失败，把 sudo nginx -t、sudo certbot --nginx 输出、sudo journalctl -u nginx -n 50 --no-pager 贴给我
```

## 当前已完成状态（截至 2026-04-27 HTTPS 切换后）

当前线上后端已经切换到正式域名 + HTTPS：

- ICP 备案号：`鄂ICP备2026020960号-1`
- 域名：
  - `jibao.tech`
  - `www.jibao.tech`
- DNS A 记录已指向：`8.136.145.232`
- `certbot --nginx -d jibao.tech -d www.jibao.tech` 已成功
- Let’s Encrypt 证书路径：
  - `/etc/letsencrypt/live/jibao.tech/fullchain.pem`
  - `/etc/letsencrypt/live/jibao.tech/privkey.pem`
- 当前证书到期日：`2026-07-26`
- `certbot` 自动续期定时任务已安装
- `Nginx` 当前已启用：
  - `HTTP -> HTTPS` 自动跳转
  - `HTTPS -> 127.0.0.1:8000 -> Docker container vita-backend`

当前外部已验证：

- `https://jibao.tech/api/v1/health`
- `https://www.jibao.tech/docs`
- `http://jibao.tech/docs` 会自动跳转到 `https://jibao.tech/docs`

当前真实链路：

```text
Browser / APK
  -> https://jibao.tech:443
  -> Nginx
  -> 127.0.0.1:8000 on host
  -> Docker container vita-backend
  -> FastAPI
```

当前建议统一使用的 API 基地址：

```text
https://jibao.tech/api/v1
```

Swagger：

```text
https://jibao.tech/docs
```

## 第 14 步：公安联网备案

现在更适合继续做公安联网备案，因为你已经有：

- ICP 备案号
- 正式域名
- 可公网访问的 HTTPS 地址

推荐在公安备案表单里填写的访问地址：

```text
https://jibao.tech/docs
```

补充提醒：

- 公安备案中的“域名证书”通常是域名注册证书/域名所有权证明，不是 SSL 证书
- 如果审核人员直接访问首页 `/`，当前可能看到后端 `404` JSON；如果你想提高观感，后续可以给 `/` 增加一个简单首页
