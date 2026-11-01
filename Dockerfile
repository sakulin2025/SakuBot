ARG BASE_IMAGE=python:3.13-slim
ARG NODE_IMAGE=node:alpine3.23
FROM ${NODE_IMAGE} AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY sakubot/plugins/ /sakubot/plugins/
COPY sakubot/system/ /sakubot/system/
COPY extensions/ssh_devices/ /preinstalled/ssh_devices/
COPY extensions/qweather/ /preinstalled/qweather/
COPY extensions/deepseek_balance/ /preinstalled/deepseek_balance/
COPY extensions/alist_manage/ /preinstalled/alist_manage/
COPY extensions/ha_control/ /preinstalled/ha_control/
COPY extensions/minecraft_status/ /preinstalled/minecraft_status/
RUN npm run build
RUN node build-plugins.mjs /preinstalled

FROM ${BASE_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SAKUBOT_DATA=/data
WORKDIR /app
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends ca-certificates curl git jq ripgrep nodejs npm ffmpeg sqlite3 && rm -rf /var/lib/apt/lists/*
RUN apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends poppler-utils libreoffice-writer libreoffice-calc fonts-liberation fonts-noto-cjk fonts-wqy-zenhei && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock
COPY extensions/requirements.txt extensions/requirements.lock ./extension-dependencies/
RUN pip install --no-cache-dir -r extension-dependencies/requirements.txt -c extension-dependencies/requirements.lock -c requirements.lock
COPY requirements-qq.txt ./
RUN pip install --no-cache-dir -r requirements-qq.txt
COPY sakubot ./sakubot
COPY --from=frontend /frontend/dist/ ./sakubot/static/
COPY --from=frontend /sakubot/plugins/ ./sakubot/plugins/
COPY --from=frontend /sakubot/system/ ./sakubot/system/
COPY --from=frontend /preinstalled/ ./preinstalled/
RUN useradd --uid 1000 --create-home sakubot && mkdir /data && chown sakubot:sakubot /data
ENV USER=sakubot LOGNAME=sakubot
USER sakubot
EXPOSE 6190
CMD ["python", "-m", "sakubot"]
