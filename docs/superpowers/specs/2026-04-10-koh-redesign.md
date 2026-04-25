# Asuri Major 完全重构设计规格

**日期**：2026-04-10  
**状态**：已确认，待实施  
**目标**：玩法不变，更公平 / 更好玩 / 更有挑战性 / 更易维护部署

---

## 1. 游戏规则与公平性

### 1.1 地图池

每轮开始时，系统用 `hash("layout", round_id, map_idx)` 预生成 **7 张地图**，提前公示。  
每张地图随机生成：出生点（双方曼哈顿距离 ≥ 12）、目标点、5 个障碍。  
地图在轮次内对所有对局共享（公平），轮次间不同（防止过拟合）。

### 1.2 策略窗口（Strategy Window）

轮次开始后开放 **10 分钟策略窗口**，队伍可：
1. 更新攻守权重（沿用现有上传逻辑）
2. 提交 BP 偏好（新增）：
   ```json
   {
     "ban_priority": [map_id, ...],
     "pick_priority": [map_id, ...],
     "role_preference": { "map_id": "attack|defense|either", ... }
   }
   ```
   未提交的队伍使用随机默认值，窗口关闭后系统自动解析，不等待。

### 1.3 BP 解析（对每对 A vs B 独立运行）

镜像 CS:GO Major 格式，ELO 较低方为 T1（先手）：

```
T1 ban → T2 ban → T1 pick+角色 → T2 pick+角色 → T1 ban → T2 ban → 决胜图
(7张)     (6张)    (5张)          (4张)          (3张)    (2张)    (1张)
```

决胜图角色：`seeded_random(round_id, team_a, team_b)`  
结果：BO3，Map1（T1主场）、Map2（T2主场）、Map3（决胜）。

### 1.4 对局格式：BO3

每张地图上各打 **2 场**（角色互换），2 场得分之和决定该地图胜负（3-0/3赢, 0-3/0赢, 1-2或2-1看总分）。  
先赢 2 张地图者为本轮 BO3 胜者。

### 1.5 ELO 天梯

- 初始 ELO：1000，K=32
- BO3 胜负结果更新 ELO（W=1, D=0.5, L=0）
- ELO 决定 BP 先手顺序（低 ELO 先 ban）
- 排行榜：ELO / 胜场 / 平场 / 负场 / 攻击胜率 / 防守胜率

### 1.6 公平性改进

| 问题 | 改法 |
|------|------|
| 固定出生点 | 每张地图随机，round 内共享 |
| 超时攻击方赢 | 超时 → 平局 |
| 全局视野 | Fog of War：可见半径 6（曼哈顿），未知格用哨兵值 `-1` 填充，obs_dim=13 不变 |
| 障碍太少 | 3 → 5，碰壁反弹而非原地停 |
| 策略趋同 | 提供自博弈训练脚本 `train_selfplay.py`（历史最优权重对手池） |

---

## 2. 后端架构

### 2.1 技术栈

| 层 | 现在 | 改后 |
|----|------|------|
| Web 框架 | Flask（同步） | **FastAPI**（async） |
| 存储 | state.json | **PostgreSQL** |
| 任务队列 | 无（HTTP 同步） | **Celery + Redis** |
| WebSocket | 无 | **FastAPI WebSocket + Redis pub/sub** |
| 包管理 | uv | 沿用 uv |
| 前端构建 | Vite+pnpm | 沿用 |

### 2.2 服务拓扑

```
React SPA
   │  HTTP REST + WebSocket
   ▼
FastAPI (api) ─── Celery Beat (scheduler)
   │                    │ 定时触发策略窗口关闭/结算
   ▼                    ▼
PostgreSQL       Celery Worker (match-runner)
   ▲                    │ 写结果
   └────────────────────┘
         Redis (broker + pub/sub)
```

### 2.3 数据模型（PostgreSQL 表）

```
users           id, username, password_hash, is_admin, is_active, elo, created_at
sessions        token, user_id, expires_at
rounds          id, status, strategy_opens_at, strategy_closes_at, created_at
maps            id, round_id, map_idx, seed, layout_json
submissions     id, user_id, round_id, role, stored_path, uploaded_at
bp_preferences  id, user_id, round_id, ban_priority, pick_priority, role_preference
matches         id, round_id, map_id, team_a_id, team_b_id, status, result_json
replays         id, match_id, map_id, frames_path
elo_history     id, user_id, round_id, elo_before, elo_after, delta
```

### 2.4 Celery 任务

```
koh.tasks.open_strategy_window(round_id)   # Celery Beat 定时触发
koh.tasks.close_strategy_window(round_id)  # 解析 BP，生成所有 match 记录
koh.tasks.run_match(match_id)              # 跑单场比赛，写结果，发布 WS 事件
koh.tasks.finalize_round(round_id)         # 汇总得分，更新 ELO
```

`close_strategy_window` 完成后，用 Celery `group()` 并发派发所有 `run_match` 任务，K8s 上 Worker Deployment 横向扩展消费。

### 2.5 WebSocket 实时直播

- 客户端连接 `ws://api/ws/rounds/{round_id}/live`
- `run_match` 每运行一步，向 Redis channel `round:{round_id}:frames` 发布帧数据
- FastAPI WS handler 订阅 Redis，推送给所有连接客户端
- 前端渲染实时棋盘动画（复用现有 Board 组件）

---

## 3. API 设计

所有接口返回 `{"ok": bool, "data": ...}`，沿用现有约定。

### 新增接口

```
GET  /api/rounds/{id}/maps              # 查看本轮 7 张地图
POST /api/rounds/{id}/bp               # 提交 BP 偏好（策略窗口内）
GET  /api/rounds/{id}/bp               # 查看自己的 BP 偏好
GET  /api/rounds/{id}/matches          # 本轮所有对局状态
GET  /api/matches/{id}                 # 单场对局详情 + 结果
WS   /ws/rounds/{id}/live              # 实时帧推送
GET  /api/leaderboard                  # 新增 elo / elo_delta 字段
GET  /api/users/{username}/elo-history # ELO 历史曲线数据
```

### 变更接口

```
GET /api/status  # 新增 strategy_window_open/closes_at/maps 字段
```

---

## 4. 前端 UI

### 4.1 页面结构（沿用 SPA，新增视图）

```
/dashboard     选手面板（改造）
/admin         管理后台（改造）
/arena         实时直播大屏（新增）★
/replays/:id   回放（改造：更好的棋盘动画）
```

### 4.2 选手面板改造重点

- **地图池展示**：7 张地图缩略图（显示障碍/目标/出生点），策略窗口内可点击设置 ban/pick/角色偏好
- **BP 偏好编辑器**：拖拽排序 ban/pick 优先级，每张地图选角色偏好
- **策略窗口倒计时**：窗口关闭前醒目提示
- **ELO 折线图**：历史 ELO 变化

### 4.3 实时直播大屏（/arena）★

- 左侧：当前轮次所有对局状态列表（进行中 / 完成 / 排队中）
- 右侧：点击任意对局，右侧播放该对局实时帧动画（WebSocket 驱动）
- 棋盘：有颜色区分（攻击方红，防守方蓝，Fog of War 遮罩灰色区域）
- 底部：ELO 实时排行榜（每局结束后刷新）

### 4.4 回放页改造

- 棋盘加 Fog of War 遮罩（分攻守双方视角切换）
- 显示 BP 解析过程（ban 哪些图，pick 哪些图，角色选择）

---

## 5. 部署方案

### 5.1 本地开发（Docker Compose）

```yaml
services:
  db:       postgres:16-alpine
  redis:    redis:7-alpine
  api:      FastAPI (uvicorn, hot-reload)
  worker:   Celery worker (watchfiles)
  beat:     Celery beat (定时任务)
  frontend: Vite dev server (pnpm dev, 代理 /api → api:8000)
```

一条命令：`docker compose up`，无需手动配环境变量（`.env.example` 提供模板）。

### 5.2 K8s 生产部署

```
Deployment: koh-api      (replicas: 2+, HPA by CPU)
Deployment: koh-worker   (replicas: 2+, HPA by queue depth)
Deployment: koh-beat     (replicas: 1, 唯一调度器)
Deployment: redis        (replicas: 1, 或用托管 Redis)
StatefulSet: postgres    (replicas: 1, 或用托管 PG)
```

- API 和 Worker 真正可多副本，数据库处理并发冲突
- 不再需要 `strategy: Recreate`，支持滚动更新
- Helm chart 封装所有 K8s 资源（`helm install koh ./charts/koh`）

### 5.3 Dockerfile 策略

- 共用 base image（Python 3.11 + uv + 依赖层）
- `CMD` 参数区分 api / worker / beat，复用同一镜像
- 前端单独 Nginx 镜像，或构建后 `COPY` 进 api 镜像静态目录

---

## 6. 训练辅助

### 新增 train_selfplay.py

```python
# 对手池：维护历史最优权重列表，每 episode 随机抽一个作为对手
# 支持 --role attack/defense，--pool-dir ./checkpoints/
```

### 本地 benchmark

```bash
python -m koh.benchmark --weights my_weights.pth --role attack --episodes 100
# 输出：vs scripted_bot 胜率 / vs random 胜率
```

---

## 7. 实施范围边界

**保持不变**：
- 游戏核心逻辑（15×15 格，5 动作，DQN 接口，`.pth/.pt` 格式）
- 权重验证逻辑（`WeightPolicy.validate_submission`）
- 管理员功能（批量注册、禁用账号等）

**不做**：
- 换模型架构（选手继续用 DQN，平台只负责跑推理）
- 多语言支持
- 移动端适配
