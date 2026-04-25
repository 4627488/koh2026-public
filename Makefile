# Asuri Major 竞赛平台 Makefile
# 用法：make <目标>

IMAGE_NAME  ?= koh-ctf
DEPS_IMAGE_NAME ?= $(IMAGE_NAME)-deps
IMAGE_TAG   ?= latest
UV_LOCK_HASH ?= $(shell sha256sum uv.lock | cut -c1-12)
DEPS_IMAGE_TAG ?= deps-$(UV_LOCK_HASH)
BUILD_VERSION ?= $(shell git rev-parse --short HEAD)$$(test -n "$$(git status --porcelain --untracked-files=normal)" && printf '%s' '-dirty')
CONTAINER_NAME ?= koh-ctf-dev
DATA_DIR    ?= $(PWD)/data
PORT        ?= 8000

.PHONY: help sync lock dev dev-all worker beat db-upgrade db-revision build-base build push run stop logs clean sync-public

help:  ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ── 本地开发 ────────────────────────────────────────────────
sync:  ## 安装/更新依赖（创建 .venv）
	uv sync --no-dev

lock:  ## 更新并提交依赖锁文件（uv.lock）
	uv lock

dev:   ## 本地运行 FastAPI（需先执行 make sync）
	uv run uvicorn koh.app:app --host 0.0.0.0 --port $(PORT) --reload --reload-dir src/koh --reload-exclude "frontend/data/postgres/*"

VITE_HOST ?= localhost
WORKER_POOL ?= threads
WORKER_CONCURRENCY ?= 8
WORKER_EXTRA_ARGS ?= --without-mingle

dev-all: ## 同时启动前后端（FastAPI :8000 + Vite :5173），Ctrl+C 全部退出；VITE_HOST=0.0.0.0 可对外监听
	@trap 'kill 0' INT; \
	uv run uvicorn koh.app:app --host 0.0.0.0 --port $(PORT) --reload --reload-dir src/koh --reload-exclude "frontend/data/postgres/*" & \
	cd frontend && VITE_HOST=$(VITE_HOST) pnpm dev; \
	wait

worker: ## 启动 Celery Worker
	uv run celery -A koh.celery_worker:celery_app worker --loglevel=info --pool=$(WORKER_POOL) --concurrency=$(WORKER_CONCURRENCY) $(WORKER_EXTRA_ARGS)

beat: ## 启动 Celery Beat
	uv run celery -A koh.celery_worker:celery_app beat --loglevel=info

db-upgrade: ## 执行数据库迁移到最新版本
	uv run alembic -c alembic.ini upgrade head

db-revision: ## 生成新的迁移文件（用法：make db-revision MSG="add field"）
	uv run alembic -c alembic.ini revision -m "$(MSG)"

# ── Docker ─────────────────────────────────────────────────
build-base:  ## 构建依赖基础镜像（由 uv.lock 哈希标识）
	docker build -f Dockerfile.base -t $(DEPS_IMAGE_NAME):$(DEPS_IMAGE_TAG) .

build: build-base ## 构建业务镜像（自动复用依赖基础镜像）
	docker build \
		--build-arg BASE_IMAGE=$(DEPS_IMAGE_NAME):$(DEPS_IMAGE_TAG) \
		--build-arg BUILD_VERSION=$(BUILD_VERSION) \
		-t $(IMAGE_NAME):$(IMAGE_TAG) .

push:  ## 推送镜像到仓库（需先设置 IMAGE_NAME）
	docker push $(IMAGE_NAME):$(IMAGE_TAG)

run:  ## 本地运行容器（映射 data 目录）
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):8000 \
		-v $(DATA_DIR):/app/data \
		-e KOH_ADMIN_USERNAME=admin \
		-e KOH_ADMIN_PASSWORD=ChangeMeLocalOnly123! \
		$(IMAGE_NAME):$(IMAGE_TAG)
	@echo "服务已启动: http://localhost:$(PORT)"

stop:  ## 停止并删除本地容器
	docker rm -f $(CONTAINER_NAME) 2>/dev/null || true

logs:  ## 查看容器日志
	docker logs -f $(CONTAINER_NAME)

sync-public:  ## 同步引擎到前端静态目录（改完 koh_env.py 后执行）
	cp src/koh/game/koh_env.py frontend/public/koh_env.py
	cp src/koh/game/koh_env.py src/koh/static/app/koh_env.py

clean:  ## 清理本地虚拟环境和缓存
	rm -rf .venv __pycache__ src/__pycache__
