ARG BASE_IMAGE=koh-ctf-deps:dev

# ============================================================
# 阶段 1：前端构建
# ============================================================
FROM node:20-slim AS frontend-builder

ARG BUILD_VERSION=dev
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

WORKDIR /app/frontend

RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --prod=false

COPY frontend/ ./
RUN mkdir -p /app/src/koh/static && VITE_APP_VERSION="${BUILD_VERSION}" pnpm build

# ============================================================
# 阶段 2：运行时镜像
# 业务镜像直接复用依赖基础镜像，避免每次发版都重传 .venv / torch 大层。
# ============================================================
FROM ${BASE_IMAGE} AS runtime

# ARG 置于重型 COPY 之后：BUILD_VERSION 每次变化只使后续轻量层失效
ARG BUILD_VERSION=dev

ENV KOH_VERSION="${BUILD_VERSION}"

# 应用代码层（轻量，每次发版只推这层）
COPY --chown=koh:koh src/ ./src/
COPY --chown=koh:koh migrations/ ./migrations/
COPY --chown=koh:koh alembic.ini ./

# 前端构建产物必须最后覆盖仓库内的静态文件，避免旧 app.js 被 src/ 覆盖回去。
RUN rm -rf /app/src/koh/static/app
COPY --from=frontend-builder --chown=koh:koh /app/src/koh/static/app /app/src/koh/static/app

EXPOSE 8000

CMD ["python", "-m", "koh"]
