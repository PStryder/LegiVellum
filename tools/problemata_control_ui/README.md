# Problemata Control UI

FastAPI + static frontend for creating and validating Problemata specs.

## Run

```powershell
python -m tools.problemata_control_ui.server
```

Open: `http://localhost:8088`

Default storage backend is Postgres (`PROBLEMATA_STORAGE_BACKEND=postgres`).
Set `PROBLEMATA_STORAGE_BACKEND=memory` for local in-memory mode.

Auth behavior:

- Default mode is `LEGIVELLUM_AUTH_MODE=auto` (local/test requests bypass auth).
- For strict mode, set `LEGIVELLUM_AUTH_MODE=strict` and pass `X-API-Key`.
- Accepted dev/test key patterns include `dev-key-<tenant_id>` and `test-key-<tenant_id>`.

Optional environment variables:

- `PROBLEMATA_DATABASE_URL` (defaults to `DATABASE_URL`)
- `PROBLEMATA_AUTO_MIGRATE` (`true`/`false`, default `true`)

## API

- `GET /api/health`
- `POST /api/problemata/preview`
- `POST /api/problemata/validate`
- `POST /api/problemata/diagnostics`
- `POST /api/problemata`
- `PUT /api/problemata/{problemata_id}`
- `POST /api/problemata/from-blueprint`
- `GET /api/problemata`
- `GET /api/problemata/{problemata_id}`
