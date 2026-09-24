#!/usr/bin/env bash
# Start TigerGraph Community Edition locally (without docker compose) and wait until it answers.
set -euo pipefail
docker run -d --name verdict-tigergraph -p 14240:14240 --ulimit nofile=1000000:1000000 tigergraph/community:4.2.5 >/dev/null 2>&1 \
  || docker start verdict-tigergraph >/dev/null
echo -n "waiting for TigerGraph"
until curl -sf -u tigergraph:tigergraph http://localhost:14240/api/ping >/dev/null; do echo -n "."; sleep 5; done
echo " ready"
