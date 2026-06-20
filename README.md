# Pandocs Backend

Django REST + Channels backend for **Pandocs Markdown Editor** — powers anonymous, sign-up-free collaborative rooms, server-side revision history, workspace backup import, PDF export, and real-time WebSocket sync.

This is the companion service for the [pandocs-frontend](https://github.com/BertinAm/pandocs-frontend) React app. See [`backend.md`](backend.md) for the original architectural specification this implementation follows.

---

## Features

- **Anonymous collaborative rooms** — no user accounts required, rooms identified by a generated ID
- **Guest presence heartbeats** — track who's actively viewing/editing a room
- **Server-side revision history** — manual snapshot, list, and rollback of document content
- **Workspace backup/restore** — bulk JSON import compatible with the frontend's portable backup format
- **PDF export** — converts a room's markdown to a styled PDF (or HTML fallback if the optional PDF dependency isn't installed)
- **Real-time WebSocket sync** — Django Channels consumer broadcasts edits to all peers in a room (optional, requires `channels` + Redis)
- **Database-agnostic** — SQLite by default, drop-in PostgreSQL via `DATABASE_URL`

---

## Tech Stack

| Layer | Tool |
|---|---|
| Framework | Django 4.2 |
| API | Django REST Framework |
| Real-time | Django Channels (optional) |
| CORS | django-cors-headers |
| Static files | WhiteNoise |
| Database | SQLite (dev) / PostgreSQL (prod, via `dj-database-url`) |

---

## Project Structure

```
pandocs_backend/
├── manage.py
├── requirements.txt
├── .env.example
├── pandocs_backend/
│   ├── settings.py        # CORS, DRF, Channels, WhiteNoise, dotenv
│   ├── urls.py             # /admin/ + /api/
│   └── asgi.py             # HTTP + WebSocket routing
├── rooms/
│   ├── models.py           # CollaborativeRoom, GuestPresence, DocumentRevision
│   ├── serializers.py
│   ├── views.py            # ViewSet + PDF export view
│   ├── urls.py              # DRF router + PDF endpoint
│   ├── consumers.py        # WebSocket consumer (real-time sync)
│   ├── routing.py          # ws/collab/<room_id>/
│   └── management/commands/
│       └── seed_rooms.py   # python manage.py seed_rooms
└── templates/
    └── pdf_template.html   # Styled HTML template for PDF rendering
```

---

## Local Development

**Prerequisites:** Python 3.10+

```bash
# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run migrations and seed a default room
python manage.py migrate
python manage.py seed_rooms

# Start the dev server
python manage.py runserver
```

The API is available at `http://localhost:8000/api/`.

### Optional: enable real-time WebSocket sync

```bash
pip install channels channels-redis daphne
```

Then set `REDIS_URL` in `.env` and run a local Redis instance. Without these, the server still runs fine — it just serves HTTP only.

### Optional: enable styled PDF export

```bash
pip install xhtml2pdf
```

Without it, the `/export-pdf/` endpoint returns the rendered HTML instead of a binary PDF, so the route stays testable either way.

---

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev key | Set a strong secret in production |
| `DEBUG` | `True` | Set to `False` in production |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated list of allowed hosts |
| `DATABASE_URL` | unset (SQLite) | PostgreSQL connection string for production |
| `REDIS_URL` | `redis://127.0.0.1:6379` | Required for multi-process WebSocket channel layer |
| `CORS_EXTRA_ORIGINS` | unset | Comma-separated extra allowed frontend origins |

---

## API Reference

Base path: `/api/`

| Method | Endpoint | Description |
|---|---|---|
| `GET` `POST` | `/rooms/` | List / create collaborative rooms |
| `GET` `PUT` `PATCH` `DELETE` | `/rooms/<id>/` | Retrieve / update / delete a room |
| `POST` | `/rooms/<id>/pulse/` | Refresh a guest's presence heartbeat |
| `GET` | `/rooms/<id>/revisions/` | List server-side revision snapshots |
| `POST` | `/rooms/<id>/save-revision/` | Snapshot current room content |
| `POST` | `/rooms/<id>/rollback/` | Restore room content to a prior revision |
| `POST` | `/rooms/backup/` | Bulk import a portable JSON workspace backup |
| `GET` | `/rooms/<id>/export-pdf/` | Download the room's markdown as a PDF |
| `WS` | `/ws/collab/<room_id>/` | Real-time collaborative edit broadcast (requires Channels) |

### Example: heartbeat pulse

```bash
curl -X POST http://localhost:8000/api/rooms/default-welcome-room/pulse/ \
  -H "Content-Type: application/json" \
  -d '{"peer_id": "client-992f", "name": "Jada Gamble", "color_class": "bg-indigo-600", "avatar_style": "pixel-art"}'
```

### Example: save and roll back a revision

```bash
# Snapshot
curl -X POST http://localhost:8000/api/rooms/default-welcome-room/save-revision/ \
  -H "Content-Type: application/json" \
  -d '{"updated_by_name": "Jada Gamble"}'

# List revisions
curl http://localhost:8000/api/rooms/default-welcome-room/revisions/

# Roll back
curl -X POST http://localhost:8000/api/rooms/default-welcome-room/rollback/ \
  -H "Content-Type: application/json" \
  -d '{"revision_id": "paste-revision-uuid-here"}'
```

### Example: workspace backup import

```bash
curl -X POST http://localhost:8000/api/rooms/backup/ \
  -H "Content-Type: application/json" \
  -d '{"files": [{"id": "restored-doc-1", "name": "Restored Document.md", "content": "# Restored content"}]}'
```

---

## Deploying to Render

This repo ships with a [`render.yaml`](render.yaml) blueprint and a [`build.sh`](build.sh) build script — Render can deploy it with minimal manual setup.

### Option A — Render Blueprint (recommended)

1. Push this repo to GitHub.
2. In the Render dashboard, click **New → Blueprint** and select this repo.
3. Render reads `render.yaml` and provisions:
   - A **Web Service** running `gunicorn pandocs_backend.wsgi:application`
   - A free **PostgreSQL** database, auto-wired via `DATABASE_URL`
4. Update `CORS_EXTRA_ORIGINS` in `render.yaml` (or the dashboard) to your actual deployed frontend URL.
5. Deploy. Render runs `build.sh` (`pip install`, `collectstatic`, `migrate`) automatically on every deploy.

### Option B — Manual Web Service

1. **New → Web Service**, connect this repo.
2. **Build Command:** `./build.sh`
3. **Start Command:** `gunicorn pandocs_backend.wsgi:application`
4. Add environment variables:
   - `DJANGO_SECRET_KEY` — generate a strong random value
   - `DEBUG` = `False`
   - `DATABASE_URL` — from a Render PostgreSQL instance (or omit to fall back to SQLite, **not recommended** for production since Render's disk is ephemeral)
   - `CORS_EXTRA_ORIGINS` — your frontend's deployed origin
5. Deploy.

### Notes on Render limitations

- **WebSocket real-time sync** (`channels` + Redis) requires Render's paid tiers if you need a managed Redis add-on, or an external Redis provider (e.g. Upstash). The app degrades gracefully to HTTP-only without it.
- **SQLite is not durable** on Render's free web service disk — always attach the PostgreSQL add-on (included in `render.yaml`) for anything beyond a quick demo.
- `ALLOWED_HOSTS` automatically includes Render's injected `RENDER_EXTERNAL_HOSTNAME`, so no manual host configuration is needed for the default domain.

---

## General Deployment Notes

- Run `python manage.py collectstatic` before deploying — static files are served via WhiteNoise.
- Set `DEBUG=False` and a real `DJANGO_SECRET_KEY` in production.
- Point `DATABASE_URL` at a managed PostgreSQL instance for durable storage.
- For real-time sync at scale, run Django Channels behind `daphne`/`uvicorn` with a managed Redis instance, and route WebSocket traffic separately from HTTP if your platform requires it.
- Set `CORS_EXTRA_ORIGINS` to your deployed frontend's origin (e.g. the Vercel URL).

See [`backend.md`](backend.md) for the original detailed architecture spec, including the full WebSocket consumer design and anonymous room sweeper considerations.
