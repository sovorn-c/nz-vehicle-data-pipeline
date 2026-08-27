#!/usr/bin/env bash
set -euo pipefail

STARTUP_ONLY=false
if [[ "${1:-}" == "--startup-only" ]]; then
    STARTUP_ONLY=true
fi

cleanup() {
    echo "==> Cleaning up Compose resources..."
    docker compose down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "==> Starting PostgreSQL, Migrations, and API via Docker Compose..."
docker compose down -v --remove-orphans >/dev/null 2>&1 || true
docker compose up -d --build api

echo "==> Waiting for API /ready endpoint..."
READY=false
for i in $(seq 1 30); do
    if curl -s -f http://localhost:8000/ready >/dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 1
done

if [[ "$READY" != "true" ]]; then
    echo "ERROR: API /ready endpoint did not respond successfully within 30 seconds."
    docker compose logs
    exit 1
fi

echo "==> API is ready. Checking /health..."
HEALTH_RESP=$(curl -s http://localhost:8000/health)
if [[ "$HEALTH_RESP" != '{"status":"ok"}' ]]; then
    echo "ERROR: Unexpected /health response: $HEALTH_RESP"
    exit 1
fi

if [[ "$STARTUP_ONLY" == "true" ]]; then
    echo "==> Startup-only check passed successfully!"
    exit 0
fi

echo "==> Executing seed command (Run 1)..."
docker compose run --rm seed

echo "==> Executing seed command (Run 2 - Idempotency)..."
docker compose run --rm seed

echo "==> Verifying OpenAPI scenarios..."

# 1. Clean vehicle
echo "Checking Clean Vehicle (1HGCR2F85HA000000)..."
CLEAN_JSON=$(curl -s http://localhost:8000/v1/vehicles/1HGCR2F85HA000000)
if ! echo "$CLEAN_JSON" | grep -q '"make":"HONDA"'; then
    echo "ERROR: Clean vehicle missing HONDA make: $CLEAN_JSON"
    exit 1
fi
if ! echo "$CLEAN_JSON" | grep -q '"stolen_status":"NOT_LISTED"'; then
    echo "ERROR: Clean vehicle missing NOT_LISTED stolen_status: $CLEAN_JSON"
    exit 1
fi
if echo "$CLEAN_JSON" | grep -q '"raw_payload"'; then
    echo "ERROR: Clean vehicle response leaked raw_payload!"
    exit 1
fi

# 2. Risky vehicle
echo "Checking Risky Vehicle (1FA6P8CF8H5000000)..."
RISKY_JSON=$(curl -s http://localhost:8000/v1/vehicles/1FA6P8CF8H5000000)
if ! echo "$RISKY_JSON" | grep -q '"stolen_status":"LISTED"'; then
    echo "ERROR: Risky vehicle missing LISTED stolen_status: $RISKY_JSON"
    exit 1
fi
if ! echo "$RISKY_JSON" | grep -q '"writeoff_status":"STATUTORY"'; then
    echo "ERROR: Risky vehicle missing STATUTORY writeoff_status: $RISKY_JSON"
    exit 1
fi

# 3. Unknown vehicle
echo "Checking Unknown Vehicle (JM0BL10F000000000)..."
UNK_JSON=$(curl -s http://localhost:8000/v1/vehicles/JM0BL10F000000000)
if ! echo "$UNK_JSON" | grep -q '"ppsr_result":"UNKNOWN"'; then
    echo "ERROR: Unknown vehicle missing UNKNOWN ppsr_result: $UNK_JSON"
    exit 1
fi

# 4. Conflict vehicle
echo "Checking Conflict Vehicle (WAUZZZ8K7BA000000)..."
CONF_JSON=$(curl -s http://localhost:8000/v1/vehicles/WAUZZZ8K7BA000000)
if ! echo "$CONF_JSON" | grep -q '"field_name":"ppsr_result"'; then
    echo "ERROR: Conflict vehicle missing ppsr_result conflict: $CONF_JSON"
    exit 1
fi

# 5. Observation exact evidence
echo "Checking Observation Exact Evidence (dealer XML)..."
OBS_JSON=$(curl -s http://localhost:8000/v1/observations/obs_dealer_feed_dealer_xml_LST_HYUNDAI_02)
if ! echo "$OBS_JSON" | grep -q '<dealer-listing>'; then
    echo "ERROR: Observation missing exact XML raw payload: $OBS_JSON"
    exit 1
fi

echo "==> All local smoke checks passed successfully!"
