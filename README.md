# NZ Vehicle Data Pipeline

Build canonical New Zealand vehicle records from real and synthetic sources while preserving field provenance, source conflicts, and confidence throughout reconciliation.

---

## Architecture, Provenance & Data Flow

```mermaid
flowchart TD
    subgraph Sources [Source Inputs]
        NHTSA[NHTSA vPIC JSON]
        NZTA[NZTA Fleet CSV]
        DEALER_JSON[Dealer Listing JSON]
        DEALER_XML[Dealer Listing XML]
        RISK_PPSR[Synthetic PPSR JSON]
        RISK_STOLEN[Synthetic Stolen JSON]
        RISK_WO[Synthetic Write-Off JSON]
    end

    subgraph Ingestion [Ingestion & Durable Evidence (ADR 0001)]
        CONNECTORS[Source Connectors]
        OBS_STORE[(PostgreSQL Source Observations)]
    end

    subgraph NormalizationTriage [Normalization & Triage (ADR 0002)]
        NORM[Normalization Engine]
        TRIAGE{Identity Triage: ISO 3779 VIN?}
        EVIDENCE_ONLY[Evidence Only Storage]
        ELIGIBLE[Eligible Candidates]
    end

    subgraph Reconciliation [Deterministic Reconciliation (ADR 0003)]
        EXTRACT[Candidate Extractor]
        RESOLVE[Field Resolver: Authority & Conflict Tracking]
        CONFIDENCE[Confidence Engine: Scoring & Freshness]
    end

    subgraph PersistenceAPI [Canonical Persistence & Delivery (ADR 0004)]
        CAN_STORE[(PostgreSQL Canonical Revisions)]
        FASTAPI[FastAPI Inspection API]
    end

    Sources --> CONNECTORS
    CONNECTORS --> OBS_STORE
    OBS_STORE --> NORM
    NORM --> TRIAGE
    TRIAGE -- "Truncated / Invalid" --> EVIDENCE_ONLY
    TRIAGE -- "Valid 17-char VIN" --> ELIGIBLE
    ELIGIBLE --> EXTRACT
    EXTRACT --> RESOLVE
    RESOLVE --> CONFIDENCE
    CONFIDENCE --> CAN_STORE
    CAN_STORE --> FASTAPI
```

---

## Stack

- **Language:** Python 3.12+
- **Data Modeling & Validation:** Pydantic v2 (strict frozen models)
- **API Framework:** FastAPI & Uvicorn
- **Database & Migrations:** PostgreSQL & Alembic (async SQLAlchemy with Psycopg 3)
- **Package & Workflow Tooling:** uv, pytest, Ruff, mypy
- **Containerization:** Docker & Docker Compose

---

## Quickstart & Commands

### Prerequisites
- Docker Engine & Docker Compose (or Python 3.12+ and local PostgreSQL instance)
- Astral `uv` (for local development)

### Running with Docker Compose

1. **Start Database and API (runs migrations automatically):**
   ```bash
   docker compose up -d --build api
   ```

2. **Run Deterministic Offline Seed:**
   ```bash
   docker compose run --rm seed
   ```

3. **Check Service Health & Readiness:**
   ```bash
   curl -s http://localhost:8000/health
   # {"status":"ok"}

   curl -s http://localhost:8000/ready
   # {"status":"ready","database":"connected"}
   ```

4. **Run End-to-End Local Smoke Verification:**
   ```bash
   bash scripts/smoke-local.sh
   ```

5. **Clean Up Containers & Volumes:**
   ```bash
   docker compose down -v
   ```

### Local Development Commands

| Action | Command |
|---|---|
| Run API server | `uv run uvicorn nz_vehicle_data_pipeline.api:app --reload` |
| Run full test suite | `uv run pytest` |
| Run PostgreSQL integration tests | `bash scripts/test-postgres.sh` |
| Lint and format check | `uv run ruff check . && uv run ruff format --check .` |
| Type check | `uv run mypy src tests` |
| Run all quality gates | `bash scripts/check.sh` |
| Build wheel package | `uv build` |

---

## Scenarios & API Inspection Examples

After running `seed`, the pipeline populates five canonical vehicle scenarios:

### 1. Clean Vehicle (`1HGCR2F85HA000000`)
Combined NHTSA specifications, dealer pricing, and clean risk checks (`NOT_LISTED`, `NONE`, `NO_MATCH`):
```bash
curl -s http://localhost:8000/v1/vehicles/1HGCR2F85HA000000
```
Key response fields:
- `stolen_status`: `"NOT_LISTED"`
- `writeoff_status`: `"NONE"`
- `ppsr_result`: `"NO_MATCH"`
- `confidence.band`: `"MEDIUM"` (governed by synthetic risk authority)
- `synthetic_notice`: Notice present

### 2. Risky Vehicle (`1FA6P8CF8H5000000`)
Identifies high-risk indicators across all synthetic registries:
```bash
curl -s http://localhost:8000/v1/vehicles/1FA6P8CF8H5000000
```
Key response fields:
- `stolen_status`: `"LISTED"`
- `writeoff_status`: `"STATUTORY"`
- `ppsr_result`: `"MATCH"`

### 3. Unknown Vehicle (`JM0BL10F000000000`)
Preserves epistemic honesty: `UNKNOWN` values are never inferred as clean:
```bash
curl -s http://localhost:8000/v1/vehicles/JM0BL10F000000000
```

### 4. Conflict Vehicle (`WAUZZZ8K7BA000000`)
Equal-authority disagreement between two synthetic PPSR feeds produces an unresolved conflict:
```bash
curl -s http://localhost:8000/v1/vehicles/WAUZZZ8K7BA000000
```
Key response fields:
- `canonical_fields`: `ppsr_result` is omitted
- `conflicts`: Contains unresolved conflict details with competing candidate values

### 5. Format Parity & Evidence Inspection (`KMHD35LH2JU000000`)
Demonstrates exact semantic equivalence between JSON and XML dealer listings while preserving distinct raw observations:
```bash
# Retrieve raw XML observation without payload leakage in vehicle API
curl -s http://localhost:8000/v1/observations/obs_dealer_feed_dealer_xml_LST_HYUNDAI_02
```

---

## Data Sources, Attribution & Licences

| Source System | Classification | Format | Licence / Attribution |
|---|---|---|---|
| **NHTSA vPIC** | Captured Public Evidence | REST / JSON | US Government Public Domain |
| **NZTA Motor Vehicle Register** | Captured Public Evidence | CSV | CC-BY 4.0 Waka Kotahi NZTA |
| **Dealer Listings** | Synthetic Model Data | JSON & XML | Synthetic Test Data |
| **PPSR Register** | Synthetic Risk Data | JSON | Synthetic Test Data |
| **NZ Police Stolen Vehicle** | Synthetic Risk Data | JSON | Synthetic Test Data |
| **Insurer Total-Loss Write-off** | Synthetic Risk Data | JSON | Synthetic Test Data |

### Synthetic Data Disclaimer (ADR 0005)
> **"This record represents no real vehicle, person, police report, insurance decision, or financial obligation."**

Every synthetic source record carries this mandatory disclaimer. Any canonical vehicle revision incorporating synthetic provenance includes this notice in the API output.

---

## Technical Limitations & Boundaries

1. **NZTA Fleet Register:** Open NZTA fleet snapshots publish 11-character truncated VINs (`VIN11`) and license plates without full 17-character ISO 3779 VINs. Under ADR 0002, these records are stored as immutable `EVIDENCE_ONLY` and cannot create or merge canonical vehicle records.
2. **NHTSA vPIC:** vPIC decodes provide authoritative manufacturer specifications for global vehicles, but do not provide New Zealand domestic registration, licensing, or warrant of fitness statuses.
3. **Payload Isolation:** Raw source payloads are stored immutably in `source_observations` and are accessible solely through `/v1/observations/{id}`. They are never echoed in `/v1/vehicles/{vin}` endpoints.

---

## Domain Generalization

The multi-source reconciliation, provenance tracking, and conflict resolution architecture built here generalizes directly to any multi-source entity resolution domain:
- **Commercial Registry Reconciliation:** Merging national company registries, credit scoring, and insolvency filings.
- **Supply Chain Traceability:** Reconciling freight bills of lading, customs declarations, and IoT sensor telemetry.
- **Healthcare Records Integration:** Resolving patient clinical encounters across federated health networks while maintaining immutable audit trails and conflict provenance.
