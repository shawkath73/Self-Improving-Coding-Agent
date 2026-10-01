# Verified Execution Agent

This project is a small self-improving coding agent. The **FastAPI backend** accepts benchmark tasks, asks an optional LLM to write code, executes that code, critiques the test result, and stores the run. The **React dashboard** uses a calm, accessible frosted-glass layout for starting runs and understanding the results. SQLite stores local runs by default; PostgreSQL is supported for production.

## Quick start (local development)

Requirements: Python 3.11+, Node.js 18+, and (optionally) Docker.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn verified_agent.api:app --reload
```

In a second terminal:

```powershell
npm --prefix frontend install
npm --prefix frontend run dev
```

Open the Vite URL shown in the terminal (usually `http://localhost:5173`). The development dashboard calls the API at `http://127.0.0.1:8000`. Set `VITE_API_URL` if the API is elsewhere:

```powershell
$env:VITE_API_URL = "http://localhost:8000"
```

## Production deployment

Build the frontend and let FastAPI serve the generated files:

```powershell
npm --prefix frontend run build
python -m uvicorn verified_agent.api:app --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000`. The dashboard uses same-origin API requests in a production build. Alternatively, host `frontend/dist` on a separate static server and build with `VITE_API_URL=https://your-api.example.com`; configure `CORS_ORIGINS` on the API to allow that origin.

The dashboard sections are:

- **Overview**: persisted KPIs, pass-rate trend, experiment comparison, and recent runs.
- **Runs**: create a run with `POST /runs`, then watch queued/running jobs poll until completion.
- **Experiments**: view persisted ablation JSON from the database or `results/ablations.json`.
- **Memory**: inspect successful solutions saved from passed runs.
- **Benchmarks**: browse the available task manifest.
- **Settings**: safe backend/database information; secrets are never exposed.

### Render backend + Vercel frontend (recommended)

1. Create a PostgreSQL database in [Neon](https://console.neon.tech/) or
   [Supabase](https://supabase.com/dashboard). Copy its pooled connection string
   (it starts with `postgresql://`; Neon may require `?sslmode=require`).
2. In Render, create a **Web Service** from this repository. Render detects
   `render.yaml`, or use these values manually:
   - Build command: `pip install ".[postgres,gemini,anthropic]"`
   - Start command: `uvicorn verified_agent.api:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/settings`
3. Set Render environment variables: `DATABASE_URL` to the database URL,
   `LLM_PROVIDER` (`gemini` or `anthropic`), the matching provider API key,
   and `CORS_ORIGINS` to the eventual Vercel URL (for example
   `https://my-agent.vercel.app`). Do not include a trailing slash.
4. Deploy the `frontend` directory as a Vercel project. Set
   `VITE_API_URL` to the Render service URL (for example
   `https://verified-execution-agent.onrender.com`) and run
   `npm run build`; Vercel's framework preset can be **Vite** and its output
   directory is `dist`.
5. After Vercel supplies the final domain, update Render's `CORS_ORIGINS` to
   that exact origin and redeploy. For a custom domain, use that domain instead.

`DATABASE_URL` takes precedence over `RUN_DB_PATH`; when it is absent the
application continues to use SQLite. The PostgreSQL schema is created
automatically on first boot. Neon and Supabase both work with their pooled
PostgreSQL URLs. Never expose `DATABASE_URL` or LLM keys in Vercel/frontend
environment variables.

### Docker deployment

The image installs the PostgreSQL driver, serves the built dashboard when
`frontend/dist` is present, honors Render's `PORT`, and runs as an unprivileged
user:

```powershell
docker build -t verified-agent .
docker run --rm -p 8000:8000 --env-file .env verified-agent
```

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `RUN_DB_PATH` | SQLite file location | `runs.db` |
| `DATABASE_URL` | PostgreSQL connection URL (overrides SQLite) | unset |
| `LLM_PROVIDER` | `gemini` or `anthropic` | auto-detect from key |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | Provider credential (backend only) | unset |
| `GEMINI_MODEL` / `ANTHROPIC_MODEL` | Model name | provider default |
| `LLM_TIMEOUT_SECONDS` | Provider request timeout | `60` |
| `USE_DOCKER` | Use Docker execution for full-system runs | unset |
| `CORS_ORIGINS` | Comma-separated frontend origins | `*` |
| `VITE_API_URL` | API URL for a separately hosted frontend | unset |

Never put provider keys in frontend code, commit them, or paste them into the Settings page.

## Offline evaluation

Offline evaluation is deterministic and does not call an LLM:

```powershell
python -m verified_agent.evaluation offline --output results\offline.json
```

The dashboard can display saved ablations after you persist them with the experiment API or place an `results/ablations.json` file in the project.

## SQLite reset and backup

Stop the API before copying the database. A backup is just a copy of the configured SQLite file:

```powershell
Copy-Item $env:RUN_DB_PATH .\backups\runs-$(Get-Date -Format yyyyMMdd-HHmmss).db
```

If `RUN_DB_PATH` is unset, back up `runs.db`. To reset local data, stop the server and remove the file:

```powershell
Remove-Item .\runs.db
```

The schema is recreated automatically on the next start. Do not delete `results/` if you want to retain offline experiment output.

## Optional Docker

The executor can run generated code in Docker when Docker Desktop is installed:

```powershell
$env:USE_DOCKER = "1"
python -m uvicorn verified_agent.api:app --host 0.0.0.0 --port 8000
```

The application itself does not require Docker; the default local executor is sufficient for development.

## API and validation

Important endpoints include `POST /runs`, `GET /runs`, `GET /runs/{run_id}`, `GET /dashboard/summary`, `GET /experiments/ablations`, `GET /memory`, `GET /benchmarks/tasks`, and `GET /settings`.

```powershell
pytest
ruff check .
npm --prefix frontend run typecheck
npm --prefix frontend run build
```
