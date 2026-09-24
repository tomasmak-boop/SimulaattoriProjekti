#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
pkill -f 'worker_pool.worker.main' 2>/dev/null || true
sleep 1
exec env REDIS_URL=redis://localhost:6379/0 \
    python -m worker_pool.worker.main \
        --session-id cip-smoke \
        --simulation-id cip \
        --opcua-port 5020 \
        --advertise-host 127.0.0.1 \
        --http-host 127.0.0.1