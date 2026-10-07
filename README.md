# Personal expenses agent

A tool to ask questions about my spending habits..

## Guardrails

The list of guardrails put in place.

| Layer | Type |
|---|---|
| Read-only DuckDB connection | Enforced |
| `enable_external_access: False` | Enforced |
| `lock_configuration: True` to prevent config changes | Enforced |
| SQL parse validation (single SELECT/WITH, no writes, table allowlist) | Enforced |
| 200-row cap, 10s timeout | Enforced |
| Prompt instruction (SELECT/WITH only) | Advisory |
| Query logging | Audit |

## Limitations

- Endpoint is async, but DuckDB calls are blocking.
- No auth, no per-user isolation
- A valid, but expensive query, can still use resources until the timeout hits.
