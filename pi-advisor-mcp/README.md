# PI Advisor MCP Server (Panorama)

An optimized [Model Context Protocol](https://modelcontextprotocol.io) server for
AVEVA PI System, built for fast (<5 s) natural-language querying of PI Asset
Framework (AF) data via PI Web API.

It combines three resolution layers — a **NetworkX knowledge graph**, a
**ChromaDB vector store** (BAAI/bge-base-en-v1.5 embeddings), and a **BM25
keyword index** — fused with Reciprocal Rank Fusion, plus an in-process TTL
cache, so most queries resolve to concrete PI Web API calls without an extra
LLM round-trip.

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Primary runtime |
| PI Web API | 2019+ | Reachable from this host |
| RAM | ≥ 4 GB | Embedding model uses ~430 MB |
| Disk | ~2 GB free | Model + Chroma/graph/BM25 data |
| Docker | optional | Alternative to venv |

The first run downloads the embedding model `BAAI/bge-base-en-v1.5` (~430 MB)
from Hugging Face, so the machine needs internet access **once** for setup.
After that, the only external call at runtime is to your PI Web API (and Azure
OpenAI, on the agent side).

---

## 2. Setup with a virtual environment (recommended)

```bash
# 1. Enter the project folder
cd pi-advisor-mcp

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate           # Linux / macOS
# .venv\Scripts\activate            # Windows PowerShell

# 3. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

> `prophet` and `chromadb` pull in compiled dependencies. On a fresh Ubuntu VM
> install build tools first if pip fails:
> ```bash
> sudo apt-get update && sudo apt-get install -y gcc g++ python3-dev
> ```

---

## 3. Configure connection settings

```bash
cp .env.example .env
```

Edit `.env` and fill in your PI Web API details. Minimum required:

```bash
PI_WEBAPI_URL=https://192.168.67.151/piwebapi
AF_SERVER_NAME=win-quikckmj3dq
AF_DATABASE_NAME=APAPI
DATA_SERVER_NAME=win-quikckmj3dq
PI_USERNAME=your-username
PI_PASSWORD=your-password
PI_AUTH_METHOD=basic
PI_VERIFY_SSL=false
```

**Lock down the file** (contains credentials):

```bash
chmod 600 .env
```

### Optional: index only specific branches

By default the whole AF database is indexed. To scope to specific subtrees:

```bash
INDEX_ROOT_PATHS=\\AF\APAPI\Train 1,\\AF\APAPI\Train 2
```

Only those elements and their descendants are indexed. See `.env.example` for
the trade-offs (ancestors/siblings outside the scope are not visible to graph
queries).

---

## 4. Run the server

```bash
# With the venv activated:
python pi_mcp_server.py
```

What happens on startup:

1. Validates `PI_WEBAPI_URL` and tests connectivity.
2. Tries to **load** existing graph/BM25 indexes from disk (fast restart).
3. If indexes are missing or stale (>24 h), kicks off a background indexing
   pipeline: fetch AF elements → fetch attributes (concurrently) → build the
   knowledge graph, vector store, and BM25 index. The server is usable
   immediately; indexing populates in the background.

You'll see logs like:

```
2026-05-20T09:00:00 INFO  pi_advisor — PI Advisor MCP server starting …
2026-05-20T09:00:01 INFO  pi_advisor — PI Web API connected: 1.14.0 (320 ms)
2026-05-20T09:00:01 INFO  pi_advisor — Starting background indexing pipeline …
2026-05-20T09:00:45 INFO  indexing_pipeline — === Indexing pipeline COMPLETE in 44.0 s ===
```

The server speaks MCP over **stdio** by default — it is launched and managed by
an MCP client (Hermes Agent, Claude Desktop, etc.), not run as a standalone web
service. Running `python pi_mcp_server.py` directly is mainly for verifying it
starts and indexes cleanly; it will then wait for an MCP client on stdin.

---

## 5. Connect it to an MCP client (e.g. Hermes Agent)

Add this server to your MCP client config. Use **absolute paths** to the venv
Python and the server script:

```json
{
  "mcpServers": {
    "pi-advisor": {
      "command": "/home/piagent/pi-advisor-mcp/.venv/bin/python",
      "args": ["/home/piagent/pi-advisor-mcp/pi_mcp_server.py"],
      "env": {
        "PI_WEBAPI_URL": "https://192.168.67.151/piwebapi"
      }
    }
  }
}
```

(Environment is normally read from `.env`; the `env` block is optional for
overrides.)

---

## 6. Run with Docker (alternative)

```bash
cd pi-advisor-mcp

# Build (pre-downloads the embedding model into the image)
docker build -t pi-advisor-mcp .

# Run with your .env and persistent volumes for the indexes
docker run --rm -it \
  --env-file .env \
  -v "$(pwd)/chroma_data:/app/chroma_data" \
  -v "$(pwd)/graph_data:/app/graph_data" \
  -v "$(pwd)/bm25_data:/app/bm25_data" \
  pi-advisor-mcp
```

Mounting the three data volumes lets indexes survive container restarts, so you
skip re-indexing every time.

---

## 7. Verify it's working

Once an MCP client is connected, the fastest end-to-end check is the
`get_system_health` tool, which reports PI connectivity, graph node count,
vector DB status, BM25 status, and cache hit rate.

To smoke-test indexing without an MCP client, you can run a short script in the
venv:

```bash
python -c "
import asyncio
from pi_client import get_client
print(asyncio.run(get_client().test_connection()))
"
```

A healthy result looks like:
`{'ok': True, 'response_ms': 312, 'version': '1.14.0', ...}`

---

## 8. Available tools

| Category | Tools |
|---|---|
| **Resolution (call first)** | `resolve_element_attribute` |
| **Data retrieval** | `get_current_value`, `get_recorded_values`, `get_interpolated_values`, `get_stream_summary`, `get_streamset_values`, `batch_get_current_values` |
| **Element search** | `search_elements`, `search_elements_semantic` |
| **Knowledge graph** | `get_graph_context`, `get_impact_analysis`, `get_investigation_context`, `find_instruments`, `compare_siblings` |
| **System** | `get_system_health`, `trigger_reindex` |

**Recommended query flow:** `resolve_element_attribute` (→ WebIds) →
`get_current_value` / `batch_get_current_values`. Structural questions
("what's upstream", "impact if X is down") use the graph tools directly — no PI
Web API call needed.

---

## 9. Re-indexing

The pipeline auto-refreshes every `INDEXING_REFRESH_HOURS` (default 24 h). To
force a rebuild without restarting, call the `trigger_reindex` tool from your
MCP client. To force a clean rebuild from the shell, delete the cached indexes
and restart:

```bash
rm -rf chroma_data graph_data bm25_data
python pi_mcp_server.py
```

---

## 10. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `PI_WEBAPI_URL is not set` on startup | `.env` missing or not in the current directory |
| `PI Web API 401` | Wrong `PI_USERNAME`/`PI_PASSWORD` or auth method |
| SSL errors | Set `PI_VERIFY_SSL=false` for self-signed certs (POC only) |
| `No elements resolved from INDEX_ROOT_PATHS` | Path typo — check exact AF path including `\\` prefix |
| Slow first startup | Embedding model download (~430 MB) — one-time |
| Out-of-memory on a 4 GB VM | Keep `EMBEDDING_MODEL=BAAI/bge-base-en-v1.5`; avoid the `-large` variant |

---

## Architecture overview

```
Query
  ├─ TTL cache .................. hit → <1 ms
  ├─ Hybrid resolver (no PI call, 50-150 ms)
  │    alias map → BM25 → vector → Reciprocal Rank Fusion
  ├─ Knowledge graph (NetworkX) . structural queries, <1 ms
  └─ PI Web API ................. selectedFields, concurrent batches
```

| File | Role |
|---|---|
| `config.py` | Env-driven settings |
| `synonyms.py` | PI/ISA domain synonym dictionary |
| `pi_client.py` | Async PI Web API client |
| `cache.py` | TTL LRU cache |
| `knowledge_graph.py` | NetworkX AF hierarchy graph |
| `bm25_index.py` | BM25 keyword index |
| `vector_db.py` | ChromaDB vector store |
| `hybrid_resolver.py` | 3-layer resolver + RRF |
| `indexing_pipeline.py` | Coordinated index build |
| `pi_mcp_server.py` | MCP server, tools, resources, prompts |
