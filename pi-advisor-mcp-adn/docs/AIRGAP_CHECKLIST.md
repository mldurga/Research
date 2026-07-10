# Air-gapped Deployment Checklist

Print this. Every box must be ticked before the demo.

## Phase 1 — Internet-connected prep machine

- [ ] CPython **3.12 x64** installed on the prep machine (the wheel download
      must run under 3.12 — a different minor version will refuse to resolve).
- [ ] `offline\download_bundle.ps1` (Windows) or `offline/download_bundle.sh`
      (Linux/macOS) completed without errors.
- [ ] Bundle contains:
  - [ ] `python\python-3.12.10-amd64.exe`
  - [ ] `wheels\` — ~150 wheel files (incl. `torch-*win_amd64*`, `sspilib-*`,
        `chromadb-*`, `onnxruntime-*`)
  - [ ] `models\bge-base-en-v1.5\` with `model.safetensors` (~430 MB),
        `tokenizer.json`, `config.json`, `1_Pooling\`
  - [ ] `app\` — source, `requirements-lock.txt`, `.env.example`, docs
  - [ ] `auth\jwks.json` (only if using `AUTH_MODE=entra_jwt` with a local
        JWKS file) — **re-export monthly; Microsoft rotates signing keys**
- [ ] Bundle zipped and transferred per your media-transfer procedure.
- [ ] Total size sanity check: roughly 1.5–2.5 GB.

## Phase 2 — Air-gapped Windows server install

- [ ] Server has ≥ 4 GB free RAM, ≥ 5 GB free disk.
- [ ] `app\offline\install_offline.ps1 -InstallDir C:\PIAdvisor` completed.
- [ ] Existing Python installs untouched (installer used `PrependPath=0`;
      old scripts still run).
- [ ] `offline\verify_install.py` — **all checks passed**, specifically:
  - [ ] embedding model loads offline (HF offline mode)
  - [ ] chromadb round-trip
  - [ ] calc tool works and blocks imports
- [ ] `.env` configured (from `.env.example`) and ACL-restricted.

## Phase 3 — Connectivity & identity

- [ ] `PI_WEBAPI_URL` uses the gateway **FQDN** (required for Kerberos).
- [ ] Internal CA chain exported to `certs\` and `PI_CA_BUNDLE` set;
      `PI_VERIFY_SSL=true`.
- [ ] Service account created; PI mapping grants **read-only** access to the
      in-scope AF database / points (see `docs/PI_WEBAPI_AUTH.md`).
- [ ] `pi_client` connectivity test returns `ok: True` under the service
      account identity.
- [ ] TLS for the MCP endpoint: internal-CA server certificate set
      (`MCP_SSL_CERTFILE/KEYFILE`) or reverse proxy in place.
- [ ] Windows firewall inbound rule for the MCP port (default 8443) limited
      to the Power Platform / gateway source addresses.

## Phase 4 — Service & security

- [ ] `deploy\install_service.ps1 -ServiceAccount <acct>` registered; task
      starts at boot; log file rolling in `logs\`.
- [ ] `AUTH_MODE` is `api_key` or `entra_jwt` — **never** `none`.
- [ ] Allowlist populated (`AUTH_ALLOWED_USERS` / `_GROUPS` / `_APPS`).
- [ ] Negative test: request without credentials → 401; valid token from a
      non-allowlisted user → 403 (check `logs\server.log`).
- [ ] `.env` readable only by admins + the service account.

## Phase 5 — Copilot Studio

- [ ] MCP tool added in Copilot Studio pointing at `https://…/mcp`
      (see `docs/COPILOT_INTEGRATION.md`).
- [ ] All 17 tools visible and enabled on the agent.
- [ ] Agent instructions pasted (resolve-first workflow, run_calculation for
      math).
- [ ] Agent shared ONLY with the pilot security group.
- [ ] End-to-end test: a pilot user asks a live-value question in Teams and
      gets the correct number with units + timestamp.
- [ ] First index build completed (`get_system_health` → `overall_status:
      healthy`); demo queries answer in < 5 s.

## Operational notes

- Index refreshes every `INDEXING_REFRESH_HOURS` (24 h default); force with
  the `trigger_reindex` tool after AF model changes.
- JWKS file: refresh monthly from the prep machine (Phase 1 step) — key
  rotation is the one recurring external dependency of `entra_jwt` mode.
- To update dependencies later: regenerate `requirements-lock.txt` on the
  prep machine, rebuild the bundle, rerun the installer (it reuses the
  existing Python and venv-recreates cleanly).
