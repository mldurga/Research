# PI Advisor MCP Server — ADN Edition

**A**ir-gapped **D**eployment on Wi**N**dows — a hardened variant of
[`pi-advisor-mcp`](../pi-advisor-mcp) built for a private-cloud Windows
environment with **no internet access**, integrated with **Microsoft Copilot
Studio** over MCP streamable HTTP, and restricted to a small named group of
users via Microsoft Entra ID.

Same fast-resolution engine as the base project — NetworkX knowledge graph +
ChromaDB vectors (BAAI/bge-base-en-v1.5) + BM25, fused with Reciprocal Rank
Fusion and a TTL cache — plus:

| Capability | Base edition | ADN edition |
|---|---|---|
| Transport | stdio only | stdio **or streamable HTTP** (`/mcp`) for Copilot Studio |
| Inbound auth | none | `api_key` or **Entra ID JWT + code-level allowlist** |
| PI Web API auth | basic | **Kerberos (SSPI)**, **OAuth client-credentials**, bearer, basic |
| TLS | — | direct HTTPS or reverse-proxy; internal CA bundle support |
| Embedding model | downloaded at first run | **bundled, loaded fully offline** |
| Calculations | — | `run_calculation` — restricted pandas/numpy sandbox |
| Install | pip from PyPI | **fully offline bundle** (Python installer + locked wheels + model) |
| Ops | manual | Windows scheduled-task service with auto-restart + rolling logs |

17 MCP tools total: the 15 base tools (+ 1 renumbered) plus `run_calculation`.
See `pi_mcp_server.py`'s docstring for the catalogue.

---

## How the pieces fit

```
M365 Copilot / Teams user (Entra ID, allowlisted)
      │ HTTPS
      ▼
Copilot Studio agent ──(MCP connector)──►  THIS SERVER  ──► PI Web API gateway
                                           /mcp endpoint      (Kerberos or OAuth)
                                           ├─ auth.py     — JWT/API-key gate + allowlist
                                           ├─ hybrid resolver / graph / cache
                                           └─ run_calculation (restricted)
```

Design premise: inside a locked-down tenant the only practical extension
point for Copilot is an MCP server — so **every** capability (data, search,
graph reasoning, math) is packaged as an MCP tool here. Nothing needs to be
installed on the Copilot side.

---

## Deployment in five parts

### Part 1 — Build the offline bundle (internet-connected machine)

> Needs CPython **3.12 x64** on the prep machine (wheel download must run
> under the same minor version as the target).

```powershell
# Windows prep machine (recommended)
cd pi-advisor-mcp-adn\offline
.\download_bundle.ps1 -TenantId <entra-tenant-guid> -Zip
```

```bash
# or Linux/macOS prep machine
./offline/download_bundle.sh ./bundle <entra-tenant-guid>
```

Produces `bundle\` (~2 GB): Python 3.12.10 installer, ~150 locked wheels
(win_amd64/cp312 — verified resolvable for every pin), the embedding model,
the app source, and (optionally) `auth\jwks.json` for offline token
validation. `-TenantId` is only needed for `AUTH_MODE=entra_jwt`.

Why the lock file matters: `requirements-lock.txt` was resolved specifically
for Windows/Python 3.12 (`uv pip compile --python-platform
x86_64-pc-windows-msvc`). The download scripts use `--no-deps` against it, so
pip never re-evaluates platform markers on the prep machine — this is what
makes cross-platform (Linux → Windows) bundle building safe.

### Part 2 — Transfer

Move the bundle (zip) into the air-gapped environment per your approved
media procedure.

### Part 3 — Install on the air-gapped Windows server

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\app\offline\install_offline.ps1 -InstallDir C:\PIAdvisor
```

The installer: installs Python 3.12 side-by-side (**PATH untouched — existing
Python environments and scripts keep working**), creates `C:\PIAdvisor\.venv`,
installs everything from local wheels (`pip --no-index`), copies the model,
creates `.env` from the template, restricts its ACL, and runs the
verification suite (`offline\verify_install.py`) — which proves the model
loads offline, chromadb round-trips, and the calc tool works and blocks
imports, all before you configure anything.

### Part 4 — Configure `.env`

Minimum for the Copilot scenario:

```ini
MCP_TRANSPORT=http
MCP_PORT=8443
MCP_SSL_CERTFILE=certs\server.pem       # internal-CA cert (or use IIS/ARR)
MCP_SSL_KEYFILE=certs\server.key

AUTH_MODE=entra_jwt                     # or api_key for day one
AUTH_ENTRA_TENANT_ID=<tenant-guid>
AUTH_ENTRA_AUDIENCE=api://pi-advisor-mcp
AUTH_JWKS_FILE=auth\jwks.json
AUTH_ALLOWED_GROUPS=<pilot-group-object-id>

PI_WEBAPI_URL=https://<gateway-fqdn>/piwebapi
AF_SERVER_NAME=<af-server>
AF_DATABASE_NAME=<af-db>
DATA_SERVER_NAME=<data-server>
PI_AUTH_METHOD=kerberos                 # or oauth — see docs/PI_WEBAPI_AUTH.md
PI_CA_BUNDLE=certs\internal-ca-chain.pem

EMBEDDING_MODEL=models\bge-base-en-v1.5
```

Details: `docs/PI_WEBAPI_AUTH.md` (both gateways, SPN/FQDN rules, service
account + PI mapping).

Test interactively, then install the service:

```powershell
C:\PIAdvisor\deploy\run_server.ps1                                   # console test
C:\PIAdvisor\deploy\install_service.ps1 -ServiceAccount CORP\svc-pi  # boot service
```

The service account is the Kerberos identity used against PI Web API — give
it read-only PI access.

### Part 5 — Connect Copilot Studio

Follow `docs/COPILOT_INTEGRATION.md`: two Entra app registrations, add the
MCP tool to the agent (`https://<host>:8443/mcp`), paste the agent
instructions, share the agent with the pilot group only.

Access is enforced in **four layers**; the last one is this server's own
allowlist (`AUTH_ALLOWED_USERS/GROUPS/APPS`), checked in code on every
request — anyone else gets 403 regardless of platform configuration.

Print `docs/AIRGAP_CHECKLIST.md` and tick every box.

---

## The `run_calculation` tool

Gives the agent real numerical capability (rolling averages, deviation from
target, unit conversions, cross-tag math) without shipping raw arrays through
the LLM and without arbitrary code execution:

- pre-imported only: `np`, `pd`, `math`, `statistics`, `json`, `datetime`
- AST-validated: **no** imports, file/network/OS access, or dunder access
- wall-clock timeout (10 s default) in a daemon thread; output size cap
- disable outright with `CALC_TOOL_ENABLED=false`

Example call the agent makes after fetching data:

```json
{
  "code": "df = pd.DataFrame(data['values']); result = round(float(df['Value'].mean()), 2)",
  "data_json": "{\"values\": [...output of get_recorded_values...]}"
}
```

---

## Local development / stdio mode

On any machine (internet OK), the server still runs the classic way:

```
MCP_TRANSPORT=stdio, AUTH_MODE=none, EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
python pi_mcp_server.py
```

and can be launched by any local MCP client exactly like the base edition.

## Verify a running server

```powershell
Invoke-RestMethod https://<host>:8443/healthz          # liveness, no auth
# then use the get_system_health tool from any connected MCP client
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Installer: "wheel not supported" | Target Python isn't 3.12 x64 — use the bundled installer; don't reuse an old install |
| verify: model tries to reach the internet | `EMBEDDING_MODEL` doesn't point at the bundled folder — must be a local directory |
| PI 401 with kerberos | Process not running as the mapped service account; URL uses IP instead of FQDN; SPN missing — see `docs/PI_WEBAPI_AUTH.md` |
| MCP 401 from Copilot | Wrong audience/issuer, or stale `auth\jwks.json` (re-export after key rotation) |
| MCP 403 | Caller not on the allowlist — server log shows the exact rejected claim value to add |
| Slow first answers after boot | Index building in background — check `get_system_health`; warm up before demos |
| `AUTH_MODE=none` refused | Intentional: the HTTP transport requires auth; set `api_key`/`entra_jwt` |

## File map (delta vs base edition)

| File | Role |
|---|---|
| `auth.py` | Inbound gate: API-key / Entra JWT validation + allowlist (ASGI middleware) |
| `calc_tool.py` | Restricted calculation engine |
| `pi_client.py` | + Kerberos SSPI, OAuth client-credentials, bearer, CA bundle |
| `config.py` | + server/auth/calc sections, offline model handling |
| `pi_mcp_server.py` | + HTTP transport, auth wiring, `run_calculation` tool |
| `requirements-lock.txt` | Full pin set resolved for win_amd64 / cp312 |
| `offline/` | Bundle builder (PS + bash), model downloader, offline installer, verifier |
| `deploy/` | Console runner, boot-time service installer |
| `docs/` | Copilot integration, PI gateway auth, air-gap checklist |
