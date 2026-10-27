#!/bin/sh
set -eu
sakubot_compose_file="${SAKUBOT_COMPOSE_FILE:-$HOME/ContainerService/napcat/docker-compose.yml}"
if [ ! -f "$sakubot_compose_file" ]; then
  printf 'Compose 文件不存在：%s\n请设置 SAKUBOT_COMPOSE_FILE。\n' "$sakubot_compose_file" >&2
  exit 1
fi
export SAKUBOT_UID="$(id -u)"
export SAKUBOT_GID="$(id -g)"
docker compose -f "$sakubot_compose_file" up -d --build --no-deps sakubot
printf '\nSakuBot 管理页：http://127.0.0.1:6190\n管理令牌：%s/data/sakubot/admin_token\n' "$(dirname "$sakubot_compose_file")"
