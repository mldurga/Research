# PI Web API Authentication — Kerberos and OAuth gateways

The server supports both PI Web API gateway types found in enterprise
deployments. Pick one with `PI_AUTH_METHOD` in `.env`.

An important design point for both: **PI data is always accessed as ONE
service identity**, not as the individual Copilot user. Per-user access
control happens at the MCP layer (Entra allowlist); PI-side authorization is
whatever the service identity is mapped to. For a leadership POC this is the
standard pattern — give the service identity read-only access to exactly the
AF databases/points in scope.

---

## Option A — Kerberos gateway (`PI_AUTH_METHOD=kerberos`) — recommended

Uses Windows Integrated Security via SSPI (through `pyspnego`); a SPNEGO
`Negotiate` token is attached to every request. **No passwords in config**:
the token is minted from the logon session of the account the Windows
service/scheduled task runs as.

### Checklist

1. **Service account**: a domain account, e.g. `CORP\svc-piadvisor`.
2. **PI mapping**: on the PI Data Archive / AF server, create an identity
   mapping for that account with *read-only* rights to the AF database and
   PI points in scope.
3. **SPN**: the gateway host must have the SPN `HTTP/<gateway-fqdn>`
   registered (normally already true for a working Kerberos PI Web API).
   Verify: `setspn -L <gateway-machine-or-service-account>`.
4. **Run as the service account**: `deploy\install_service.ps1
   -ServiceAccount CORP\svc-piadvisor`. Interactive testing under your own
   login uses *your* Kerberos identity instead — fine for a first smoke test.
5. `.env`:
   ```
   PI_AUTH_METHOD=kerberos
   PI_WEBAPI_URL=https://<gateway-fqdn>/piwebapi   # FQDN, not IP — Kerberos needs it
   PI_VERIFY_SSL=true
   PI_CA_BUNDLE=certs\internal-ca-chain.pem
   ```

### Notes

- **Use the FQDN in `PI_WEBAPI_URL`.** Kerberos ticket requests are made for
  `HTTP/<hostname-in-url>`; an IP address will fail (or silently fall back
  to NTLM if the gateway allows it).
- If the gateway's SPN differs from the URL host (rare; load balancers),
  set `PI_KERBEROS_HOSTNAME` (and `PI_KERBEROS_SERVICE` if not `HTTP`).
- `PI_KERBEROS_USERNAME`/`PI_KERBEROS_PASSWORD` exist as an escape hatch to
  authenticate as a different account than the process identity; prefer the
  process-identity route.
- No delegation is required: the server authenticates as itself, once, per
  request.

### Quick test (from the server, in the venv)

```powershell
.venv\Scripts\python -c "import asyncio; from pi_client import get_client; print(asyncio.run(get_client().test_connection()))"
```

Expected: `{'ok': True, 'version': '1.x.x', 'auth_method': 'kerberos', ...}`

---

## Option B — OAuth gateway (`PI_AUTH_METHOD=oauth`)

Client-credentials grant against the gateway's token endpoint; the bearer
token is cached and refreshed automatically 60 s before expiry.

1. Register/obtain a client (id + secret) authorized for the PI Web API
   resource on your identity provider.
2. `.env`:
   ```
   PI_AUTH_METHOD=oauth
   PI_OAUTH_TOKEN_URL=https://<idp>/oauth2/v2.0/token
   PI_OAUTH_CLIENT_ID=<client-id>
   PI_OAUTH_CLIENT_SECRET=<secret>
   PI_OAUTH_SCOPE=<resource>/.default        # v2-style endpoints
   # or, for v1-style endpoints that expect a resource parameter:
   PI_OAUTH_RESOURCE=<resource-uri>
   ```
3. Map the client's identity to read-only PI access, as with Option A.

Set exactly one of `PI_OAUTH_SCOPE` / `PI_OAUTH_RESOURCE` depending on what
the gateway's token endpoint expects (v2 vs v1 style).

---

## Fallbacks

- `PI_AUTH_METHOD=bearer` + `PI_BEARER_TOKEN` — a long-lived token issued
  out-of-band (useful while OAuth client provisioning is pending).
- `PI_AUTH_METHOD=basic` + `PI_USERNAME`/`PI_PASSWORD` — lab environments
  only.

## TLS to the gateway

Never ship with `PI_VERIFY_SSL=false`. Export the internal root/issuing CA
chain as PEM, place it under `certs\`, and set `PI_CA_BUNDLE=certs\<file>.pem`.
The same bundle is also used when fetching JWKS over an internal URL.
