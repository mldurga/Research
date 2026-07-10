# Connecting Microsoft Copilot to the PI Advisor MCP Server

This guide connects a Copilot Studio agent (surfaced in Microsoft 365
Copilot / Teams) to this MCP server, restricted to a small named group of
users.

## Why MCP-over-HTTP is the right integration seam

Inside a locked-down corporate/private-cloud tenant you generally cannot run
custom code inside Copilot itself — the supported extension point is exactly
what this server provides: **tools delivered over the Model Context Protocol
(streamable HTTP)**. Copilot Studio natively consumes MCP servers, so every
capability the agent needs (PI data retrieval, semantic asset search,
knowledge-graph reasoning, calculations) must be — and is — exposed as an MCP
tool on this server. No customization inside the Copilot environment is
required beyond agent instructions.

```
M365 Copilot / Teams user (Entra ID)
        │
        ▼
Copilot Studio agent  ──(MCP custom connector, HTTPS + OAuth)──►  this server /mcp
                                                                    │
                                                                    ▼
                                                              PI Web API gateway
                                                              (Kerberos or OAuth)
```

## Prerequisites

- The server installed, verified, and running with `MCP_TRANSPORT=http`
  behind **HTTPS** (Copilot Studio refuses plain HTTP). Either set
  `MCP_SSL_CERTFILE`/`MCP_SSL_KEYFILE` with a certificate issued by the
  internal CA, or put IIS/ARR in front as a TLS-terminating reverse proxy.
- The server URL reachable from the Power Platform environment. If the
  Power Platform environment cannot reach the server network directly, route
  the connector through an **on-premises data gateway** (supported for custom
  connectors, including MCP ones).
- Rights to create app registrations in the Entra tenant (or an admin to do
  it for you), and a Copilot Studio license/environment.

## Step 1 — Entra ID app registrations

Two registrations, standard OAuth "protected API + client" pattern:

1. **Server API registration** (represents this MCP server)
   - *Expose an API* → set Application ID URI, e.g. `api://pi-advisor-mcp`.
   - Add a scope, e.g. `access_as_user` (admin-consent only is fine).
   - No redirect URI, no secret needed.
2. **Connector client registration** (used by the Copilot Studio connector)
   - *Authentication* → add redirect URI
     `https://global.consent.azure-apim.net/redirect` (use the sovereign-cloud
     equivalent if your tenant runs one).
   - *Certificates & secrets* → create a client secret (record it).
   - *API permissions* → add the server API's `access_as_user` scope →
     grant admin consent.

Then configure this server's `.env`:

```
AUTH_MODE=entra_jwt
AUTH_ENTRA_TENANT_ID=<tenant-guid>
AUTH_ENTRA_AUDIENCE=api://pi-advisor-mcp
AUTH_JWKS_FILE=auth\jwks.json          # exported by the bundle script
AUTH_ALLOWED_USERS=<upn1>,<upn2>,...   # or:
AUTH_ALLOWED_GROUPS=<security-group-object-id>
AUTH_ALLOWED_APPS=<connector-client-id>
```

Notes:
- If the connector is configured for **delegated** auth, tokens arrive with
  the *end user's* identity → `AUTH_ALLOWED_USERS`/`AUTH_ALLOWED_GROUPS`
  enforcement gives you true per-user restriction in code.
- If it uses **client credentials**, all calls carry the connector app's
  identity → use `AUTH_ALLOWED_APPS`, and restrict people at the agent-sharing
  layer (Step 4).
- For a same-day POC before app registrations exist, use `AUTH_MODE=api_key`
  and a connector API-key security scheme, then switch to `entra_jwt` later —
  no code changes.

## Step 2 — Add the MCP server to a Copilot Studio agent

1. Copilot Studio → your agent → **Tools** (Actions) → **Add a tool** →
   **New tool** → **Model Context Protocol**.
2. Server URL: `https://<server-host>:8443/mcp`
3. Authentication: **OAuth 2.0** — fill in the connector client id/secret,
   authorization/token URLs for your tenant, and the scope
   `api://pi-advisor-mcp/.default` (or `access_as_user` for delegated).
   For the API-key variant choose **API key**, header name `X-API-Key`.
4. Save. Copilot Studio creates a custom connector under the hood (its
   swagger carries `x-ms-agentic-protocol: mcp-streamable-1.0`); if your
   environment requires it, attach the **on-premises data gateway** on the
   connector's connection settings.
5. All 17 tools appear in the tool list once the connection is established.
   Enable them for the agent.

## Step 3 — Agent instructions (paste into Copilot Studio)

```
You answer questions about live plant operations using the PI Advisor tools.

Rules:
1. For any natural-language asset/tag question, call resolve_element_attribute
   FIRST to get WebIds; then fetch data with get_current_value or
   batch_get_current_values.
2. For structure questions (what feeds X, what is inside Y, compare trains)
   use the knowledge-graph tools; they need no PI call.
3. Never do arithmetic yourself: fetch data, then use run_calculation.
4. Lead every answer with the number that answers the question, in business
   units, with the timestamp in local words ("today 09:30").
5. Flag values that are stale (>15 min old) or of bad quality.
6. If unsure which asset the user means, show the top candidates and ask.
```

## Step 4 — Restrict WHO can use it (layered)

| Layer | Mechanism | Where |
|---|---|---|
| 1. Agent availability | Share the agent only with a security group containing the pilot users | Copilot Studio → Share |
| 2. Connector connection | Restrict the connection/DLP policy to the same group | Power Platform admin center |
| 3. Token issuance | Optionally require assignment on the server API's enterprise application ("Assignment required" = Yes, assign the group) | Entra ID |
| 4. **This server (code-level)** | `AUTH_ALLOWED_USERS` / `AUTH_ALLOWED_GROUPS` / `AUTH_ALLOWED_APPS` — enforced on every request, logged, returns 403 | `.env` on the server |

Layer 4 is fully under your control and works even if the platform layers
are misconfigured — the server itself refuses anyone not on the list.

## Step 5 — Smoke test

From any machine that can reach the server:

```powershell
# liveness (no auth required)
Invoke-RestMethod https://<server-host>:8443/healthz

# authenticated MCP initialize (api_key mode shown)
Invoke-RestMethod -Method Post https://<server-host>:8443/mcp `
  -Headers @{ "X-API-Key" = "<key>"; "Accept" = "application/json, text/event-stream" } `
  -ContentType "application/json" `
  -Body '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}'
```

Then in Copilot Studio's test pane ask: *"What is the current inlet pressure
on <any known asset>?"* and confirm the tool-call trace shows
`resolve_element_attribute` → `get_current_value`.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Connector: "unable to reach host" | Network path from Power Platform to the server — add the on-premises data gateway, or fix firewall/DNS |
| Connector: TLS errors | Server certificate not issued by a CA the platform trusts — use an internal-CA cert and ensure the chain is served |
| Server log: `Unknown signing key id` | JWKS file is stale after a Microsoft key rotation — re-export `jwks.json` and restart |
| Server returns 403 with valid login | Caller not on the allowlist — check the exact `preferred_username`/`oid`/group claims in the server log and add them |
| Tools listed but calls time out | First call after restart may trigger index build — check `get_system_health`, or pre-warm by starting the service before the demo |
