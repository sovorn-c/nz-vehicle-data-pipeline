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

fetch_json() {
    local url="$1"
    local expected_code="${2:-200}"
    local response
    response=$(curl -s -w "\n%{http_code}" "$url")
    local http_code
    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | sed '$d')
    if [[ "$http_code" != "$expected_code" ]]; then
        echo "ERROR: Expected HTTP $expected_code from $url, got $http_code: $body" >&2
        exit 1
    fi
    if ! echo "$body" | python3 -m json.tool >/dev/null 2>&1; then
        echo "ERROR: Invalid JSON response from $url: $body" >&2
        exit 1
    fi
    echo "$body"
}

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
HEALTH_RESP=$(fetch_json "http://localhost:8000/health" 200)
if [[ "$HEALTH_RESP" != '{"status":"ok"}' ]]; then
    echo "ERROR: Unexpected /health response: $HEALTH_RESP"
    exit 1
fi

if [[ "$STARTUP_ONLY" == "true" ]]; then
    echo "==> Startup-only check passed successfully!"
    exit 0
fi

echo "==> Rebuilding seed image from the current checkout..."
docker compose --profile tools build seed

echo "==> Executing seed command (Run 1)..."
RUN1_OUTPUT=$(docker compose --profile tools run --rm seed)
echo "$RUN1_OUTPUT"

echo "==> Executing seed command (Run 2 - Idempotency)..."
RUN2_OUTPUT=$(docker compose --profile tools run --rm seed)
echo "$RUN2_OUTPUT"

# Verify Run 2 idempotency via JSON inspection
python3 -c '
import json, sys
data = json.loads(sys.argv[1])
revs_created = data.get("revisions_created")
revs_reused = data.get("revisions_reused", 0)
assert revs_created == 0, f"Expected 0 created revisions on replay, got {revs_created}"
assert revs_reused >= 1, f"Expected reused revisions on replay, got {revs_reused}"
print("==> Seed idempotency confirmed: 0 created, revisions reused.")
' "$RUN2_OUTPUT"

echo "==> Verifying OpenAPI scenarios..."

# 1. Clean vehicle (Phase 2 updated state)
echo "Checking Clean Vehicle (1HGCR2F85HA000000)..."
CLEAN_JSON=$(fetch_json "http://localhost:8000/v1/vehicles/1HGCR2F85HA000000" 200)
python3 -c '
import json, sys
data = json.loads(sys.argv[1])
rev_num = data.get("revision_number")
assert rev_num == 2, f"Expected revision 2, got {rev_num}"
assert data["canonical_fields"]["make"] == "HONDA"
assert data["canonical_fields"]["stolen_status"] == "NOT_LISTED"
assert data["canonical_fields"]["asking_price_cents"] == 1995000
assert data["canonical_fields"]["odometer_km"] == 52300
assert "raw_payload" not in data, "Leaked raw_payload in canonical vehicle response"
print("  ✓ Clean vehicle (Rev 2) verified")
' "$CLEAN_JSON"

# 1b. Multi-revision history
echo "Checking Multi-revision history (1HGCR2F85HA000000)..."
HIST_JSON=$(fetch_json "http://localhost:8000/v1/vehicles/1HGCR2F85HA000000/history" 200)
python3 -c '
import json, sys
data = json.loads(sys.argv[1])
count = len(data)
assert count == 2, f"Expected exactly 2 revisions, got {count}"
revs = [r["revision_number"] for r in data]
assert revs == [2, 1], f"Expected history [2, 1], got {revs}"
assert data[0]["canonical_fields"]["asking_price_cents"] == 1995000
assert data[1]["canonical_fields"]["asking_price_cents"] == 2150000
print("  ✓ Multi-revision history [2, 1] verified")
' "$HIST_JSON"

# 1c. Specific revision endpoints
echo "Checking Explicit Revisions /revisions/1 and /revisions/2..."
REV1_JSON=$(fetch_json "http://localhost:8000/v1/vehicles/1HGCR2F85HA000000/revisions/1" 200)
REV2_JSON=$(fetch_json "http://localhost:8000/v1/vehicles/1HGCR2F85HA000000/revisions/2" 200)
python3 -c '
import json, sys
r1 = json.loads(sys.argv[1])
r2 = json.loads(sys.argv[2])
assert r1["revision_number"] == 1 and r1["canonical_fields"]["asking_price_cents"] == 2150000
assert r2["revision_number"] == 2 and r2["canonical_fields"]["asking_price_cents"] == 1995000
print("  ✓ Explicit revision 1 and 2 retrieval verified")
' "$REV1_JSON" "$REV2_JSON"

# 1d. Catalog discovery & pagination slicing
echo "Checking Catalog Discovery & Pagination (/v1/vehicles)..."
PAGE1_JSON=$(fetch_json "http://localhost:8000/v1/vehicles?limit=2&offset=0" 200)
PAGE2_JSON=$(fetch_json "http://localhost:8000/v1/vehicles?limit=2&offset=2" 200)
python3 -c '
import json, sys
p1 = json.loads(sys.argv[1])
p2 = json.loads(sys.argv[2])
tot = p1.get("total")
p1_len = len(p1.get("items", []))
p2_len = len(p2.get("items", []))
assert tot == 5, f"Expected total 5, got {tot}"
assert p1_len == 2, f"Expected 2 items in page 1, got {p1_len}"
assert p2_len == 2, f"Expected 2 items in page 2, got {p2_len}"
vins_p1 = {item["vin"] for item in p1["items"]}
vins_p2 = {item["vin"] for item in p2["items"]}
assert vins_p1.isdisjoint(vins_p2), "Pagination overlap detected between page 1 and page 2"
for item in p1["items"] + p2["items"]:
    assert "vin" in item and "make" in item and "synthetic" in item
print("  ✓ Catalog pagination slicing verified (disjoint sets, total=5)")
' "$PAGE1_JSON" "$PAGE2_JSON"

# 2. Risky vehicle
echo "Checking Risky Vehicle (1FA6P8CF8H5000000)..."
RISKY_JSON=$(fetch_json "http://localhost:8000/v1/vehicles/1FA6P8CF8H5000000" 200)
python3 -c '
import json, sys
data = json.loads(sys.argv[1])
assert data["canonical_fields"]["stolen_status"] == "LISTED"
assert data["canonical_fields"]["writeoff_status"] == "STATUTORY"
print("  ✓ Risky vehicle verified")
' "$RISKY_JSON"

# 3. Unknown vehicle
echo "Checking Unknown Vehicle (JM0BL10F000000000)..."
UNK_JSON=$(fetch_json "http://localhost:8000/v1/vehicles/JM0BL10F000000000" 200)
python3 -c '
import json, sys
data = json.loads(sys.argv[1])
assert data["canonical_fields"]["ppsr_result"] == "UNKNOWN"
print("  ✓ Unknown vehicle verified")
' "$UNK_JSON"

# 4. Conflict vehicle
echo "Checking Conflict Vehicle (WAUZZZ8K7BA000000)..."
CONF_JSON=$(fetch_json "http://localhost:8000/v1/vehicles/WAUZZZ8K7BA000000" 200)
python3 -c '
import json, sys
data = json.loads(sys.argv[1])
assert any(c["field_name"] == "ppsr_result" for c in data["conflicts"])
print("  ✓ Conflict vehicle verified")
' "$CONF_JSON"

# 5. Observation exact evidence
echo "Checking Observation Exact Evidence (dealer XML)..."
OBS_JSON=$(fetch_json "http://localhost:8000/v1/observations/obs_dealer_feed_dealer_xml_LST_HYUNDAI_02" 200)
python3 -c '
import json, sys
data = json.loads(sys.argv[1])
assert "<dealer-listing>" in data["raw_payload"], "Raw XML payload missing"
print("  ✓ Observation raw payload verified")
' "$OBS_JSON"

echo "==> All local smoke checks passed successfully!"
