# Asuri Major 后端重构执行计划（已启动）

## 已完成（Phase 1）

1. 删除旧 Flask 后端主链路：`manager.py` 与 `web/*`。
2. 切换运行入口为 FastAPI：`python -m koh` 与 `koh_service.py` 均改为 uvicorn。
3. 新增后端基础骨架：
   - 配置：`koh/core/config.py`
   - 数据库：`koh/db/{base,session,models}.py`
   - API：`koh/api/router.py` 与 `koh/api/routes/*`
   - Celery：`koh/tasks/{celery_app,jobs}.py`
4. 更新依赖与命令：`pyproject.toml` 与 `Makefile`。

## 下一阶段（Phase 2）

1. 接入 Alembic 迁移，替代 `create_all()`。
2. 实现策略窗口调度：`open_strategy_window` / `close_strategy_window`。
3. 完整 BP 解析（7 图、低 ELO 先手、BO3 赛制）。
4. 将现有对战引擎接到 `run_match`，产生可回放帧并写库。
5. 实现 ELO 更新与排行榜统计字段（胜平负、攻防胜率）。

## 验收标准

1. `make dev` 可启动 `/api/status` 与 `/ws/rounds/{id}/live`。
2. `make worker` 与 `make beat` 可正常启动。
3. 数据模型覆盖设计规格中的所有表。
4. 新增接口均遵守返回格式：`{"ok": bool, "data": ...}`。
