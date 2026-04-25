# Asuri Major 竞赛平台

Asuri Major 对抗平台，后端基于 FastAPI + PyTorch，前端基于 React + Vite（`pnpm`）。

平台核心是“攻防双角色权重提交 + 固定轮次地图 + 自动结算 + 回放复盘”。

## 1. 玩法说明

### 1.1 角色与胜负

- 每个队伍需要提交两份模型权重：
- `attack`：攻击方策略
- `defense`：防守方策略

对局在同一张轮次地图上进行，胜负规则：

- 防守方到达目标点：防守方胜
- 攻击方捕获防守方：攻击方胜
- 任意一方撞障碍死亡：另一方胜
- 双方同回合撞障碍：平局
- 回合超时：攻击方胜（防守超时）

### 1.2 轮次与结算

- 每轮时长由服务端配置（默认 120 秒）
- 每轮结束后可自动或手动结算
- 只有同时具备“该轮截止前有效的 attack/defense 提交”的队伍参与该轮
- 结算方式：每个队伍对其他队伍进行攻防对战（不与自己对战）

### 1.3 计分规则

- 胜：3 分
- 平：1 分
- 负：0 分

同时统计：

- 总分、胜平负
- 攻击分、攻击场次
- 防守分、防守场次

### 1.4 回放

- 每场对局会保存帧级回放
- 可在 UI 中逐帧查看地图状态、动作、结果原因

## 2. 仓库结构

```text
.
├── src/                       # Python 源码（标准 src 布局）
│   └── koh/                   # 主包
├── frontend/                  # React + Vite 前端工程（pnpm）
├── charts/                    # Helm Chart
├── Dockerfile
├── Makefile
└── pyproject.toml
```

## 3. 运行要求

- Python 3.11+
- `uv`
- Node.js 20+（已在本地验证 Node 24）
- `pnpm` 10+

## 4. 本地开发

### 4.1 安装 Python 依赖

```bash
make sync
```

### 4.2 首次启动前设置管理员密码

服务首次引导会强制要求 `KOH_ADMIN_PASSWORD`（不再允许默认弱口令）。

```bash
export KOH_ADMIN_USERNAME=admin
export KOH_ADMIN_PASSWORD='CHANGE_ME_STRONG_PASSWORD'
```

### 4.3 启动服务

```bash
make dev
```

访问：

- API：`http://127.0.0.1:8000/api/status`

## 5. 前端开发（pnpm）

前端采用 React + Vite，构建产物输出到 FastAPI 包静态目录：

- 输出目录：`src/koh/static/app`
- 前端访问基址：`/static/app/`

### 5.1 安装依赖

```bash
cd frontend
pnpm install
```

### 5.2 本地前端调试

```bash
pnpm dev
```

> 前端开发模式默认由 Vite 托管。若需要与本地 API 联调，可在 Vite 中配置代理（`/api` -> FastAPI）。

### 5.3 构建并发布到静态目录

```bash
cd frontend
pnpm build
```

构建后，重新启动后端服务即可加载新前端。

## 6. Docker 部署

### 6.1 构建镜像

```bash
make build
```

### 6.2 运行容器

```bash
make run
```

默认映射：

- 端口：`8000 -> 8000`
- 数据卷：`$(PWD)/data -> /app/data`

注意：`make run` 里的默认管理员密码仅用于本地演示，正式环境必须改为强密码。

## 7. Kubernetes 部署

Helm Chart 目录：`charts/koh`

推荐部署流程：

```bash
helm upgrade --install koh charts/koh \
	--namespace koh --create-namespace \
	--set image.repository=ghcr.io/<owner>/asuri-major \
	--set image.tag=<git-sha> \
	--set-string env.databaseUrl='postgresql+psycopg://koh:***@postgresql.koh.svc.cluster.local:5432/koh' \
	--set-string env.redisUrl='redis://redis.koh.svc.cluster.local:6379/0' \
	--set-string env.adminUsername=admin \
	--set-string env.adminPassword='***' \
	--set-string env.secretKey='***'
```

### 7.1 关键配置项

- `charts/koh/values.yaml`
- 修改 `image.repository` / `image.tag`
- 修改 `ingress.host` 为实际域名
- 修改 `env.databaseUrl` / `env.redisUrl` 指向真实数据库与 Redis
- `data` 目录使用共享存储；若 API / worker 多副本，PVC 需要 RWX 存储类或对象存储挂载

### 7.2 自动化建议

- GitHub Actions 先执行 `pnpm build`，再执行 `docker build` 并推送到镜像仓库
- Helm `pre-install` / `pre-upgrade` Job 负责 `alembic upgrade head`
- API、Celery worker、Celery beat 拆成三个 Deployment，避免一个容器承载所有职责
- worker 副本数优先按队列长度或任务积压扩缩，而不是只看 CPU

## 8. 安全说明

- 首次引导必须提供 `KOH_ADMIN_PASSWORD`
- API 使用 Bearer Token 鉴权
- 上传文件限制后缀并做权重结构校验
- 回放读取做路径约束校验，防止路径穿越
- 已设置基础安全响应头（CSP / `X-Frame-Options` / `X-Content-Type-Options` 等）

## 9. 常见命令

```bash
make sync      # 安装后端依赖
make dev       # 本地启动 FastAPI
make build     # 构建 Docker 镜像
make run       # 启动容器
make stop      # 停止容器
make logs      # 查看容器日志
```

## 10. 无人值守轮次（每 10 分钟）

平台已支持自动建轮调度。启用后，Celery Beat 会定期触发自动建轮任务；轮次仍复用现有流程：开启策略窗口、关闭策略窗口、运行对局、自动结算。

### 10.1 启动要求

无人值守模式依赖两类进程同时在线：

- Celery Worker：执行对局和结算任务
- Celery Beat：定时触发自动建轮与纠偏任务

```bash
make worker
make beat
```

### 10.2 环境变量

以下变量可在 `.env` 或进程环境中设置：

- `AUTO_ROUND_ENABLED`：是否启用自动建轮（`true`/`false`，默认 `false`）
- `AUTO_ROUND_INTERVAL_MINUTES`：自动建轮间隔（默认 `10`）
- `AUTO_ROUND_STRATEGY_WINDOW_MINUTES`：策略窗口时长（默认 `10`）
- `AUTO_ROUND_MAX_OPEN_ROUNDS`：系统中允许同时处于 `strategy_window/running` 的最大轮次数（默认 `2`）
- `AUTO_ROUND_MAX_PENDING_MATCHES`：系统允许的排队+进行中对局上限，超过时跳过建轮（默认 `2000`）
- `AUTO_ROUND_TICK_SECONDS`：自动建轮检查频率（默认 `30` 秒）
- `AUTO_ROUND_RECONCILE_SECONDS`：自动纠偏检查频率（默认 `60` 秒）

### 10.3 管理端设置

管理员前端面板新增“无人值守”页签，可直接：

- 查看当前生效配置
- 在线修改并保存配置（持久化到数据库）
- 手动触发一次自动建轮任务
