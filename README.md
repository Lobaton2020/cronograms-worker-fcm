# cronograms-worker-fcm

FCM push notification worker for the cronograms (activities) app. Runs as a
Kubernetes `CronJob` every minute, queries the `tomanotas` MySQL database for
tasks scheduled for the current minute, and dispatches Firebase Cloud Messaging
push notifications to the matching device tokens.

## Status

✅ **End-to-end working.** Verified on `2026-08-08` with a real FCM token on
Android. Push delivered successfully via `fcm.googleapis.com/v1/projects/mobile-notifications-me/messages:send`.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐
│  CronJob (k3s)  │──▶│ MySQL (tomanotas)│───▶│ tareas       │
│  every 1 min    │    │ 127.0.0.1:3306  │    │ pendientes   │
└────────┬────────┘    └─────────────────┘    └──────┬───────┘
         │                                           │
         │  Firebase Admin SDK                       │
         ▼                                           │
┌─────────────────┐                                  │
│  Firebase FCM   │◀─────────────────────────────────┘
└────────┬────────┘
         ▼
   📱 Android device
```

- **Every minute**, the CronJob wakes up.
- Queries tasks where `estado = 0`, `notified_at IS NULL`, and the cronogram
  `fecha` matches **today** in `America/Bogota`, with `hora` and `minuto`
  matching the current Bogota time.
- For each candidate, sends one FCM push and marks `notified_at = NOW()`.
- `concurrencyPolicy: Forbid` guarantees no two pods run at the same time.
- `mark_notified` is idempotent (also guards `notified_at IS NULL`).

## Firebase project

This worker is wired to the Firebase project **`mobile-notifications-me`**
(not `lobmindergo` as initially documented). The service account JSON in
`secrets/firebase-sa.json` is the key for this project.

## Repository layout

```
cronograms-worker-fcm/
├── app/
│   ├── __init__.py
│   ├── config.py        # .env resolution order (root → /app/.env)
│   ├── timezone.py      # "now in Bogota" helpers
│   ├── db.py            # SQLAlchemy 2.0 Core queries
│   ├── fcm.py           # firebase-admin wrapper
│   └── worker.py        # entrypoint
├── db/
│   └── migrations/      # 2 SQL migrations (experimental)
├── deploy/
│   ├── base/            # k8s manifests (serviceaccount, cronjob)
│   └── overlays/
│       ├── prod/        # namespace: prod
│       └── dev/         # namespace: dev
├── tests/               # pytest + SQLite in-memory
├── secrets/
│   └── firebase-sa.json # NOT in git. Local-only.
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── .env.example
└── README.md
```

## Local development

Place a `.env` file at the project root (next to `README.md`). The worker
auto-discovers it via `python-dotenv.find_dotenv()`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Create your local .env
cp .env.example .env
# ... edit .env with real values ...

# Run tests with coverage
pytest -v --cov=app --cov-report=term-missing

# Smoke test (against real MySQL + real FCM)
python -m app.worker
```

### `.env` resolution order

See `app/config.py`. The path is resolved in this order:

1. `ENV_FILE` environment variable (explicit override).
2. `.env` in current working directory or any parent directory (local dev).
3. `/app/.env` (production mount point from the `tomanotas-secrets` Secret).

## Database migrations

Two migrations only. Applied to the real `tomanotas` database on
`192.168.20.240:3306` (MariaDB 11.8.6).

```bash
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < db/migrations/001_add_notified_at.sql
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < db/migrations/002_create_fcm_tokens.sql
```

| # | Migration | Purpose |
|---|---|---|
| 001 | `001_add_notified_at.sql` | Adds `notified_at` to `tarea_cronograma` + index |
| 002 | `002_create_fcm_tokens.sql` | New `fcm_tokens` table |

**Apply only once.** These are not idempotent.

### Schema additions

```sql
-- tarea_cronograma
+ notified_at   DATETIME NULL
+ INDEX idx_notified_at (notified_at)

-- fcm_tokens (new table)
  id_fcm_token_PK, id_usuario_FK, token, platform,
  created_at, updated_at
  + UNIQUE(token), INDEX(id_usuario_FK)
```

## Two FCM credentials, two different roles

A common confusion. The worker uses **two** FCM-related secrets:

| Credential | Type | Where it lives | When |
|---|---|---|---|
| **Service Account JSON** | Server key (Admin SDK) | `./secrets/firebase-sa.json` (env: `GOOGLE_APPLICATION_CREDENTIALS`) | Server-side, once at deploy |
| **Device Token** | Per-user device identifier | `fcm_tokens.token` row in MySQL | Per user, refreshed when the app installs |

The service account JSON is "the key to the post office". The device token is
"the delivery address". Each user has their own device token row.

### How the device token gets into the DB

```
📱 Flutter app
   │
   ├── FirebaseMessaging.instance.getToken()      ← Google assigns it
   │        │
   │        ▼
   ├── mutation updateFcmToken(userId, token)    ← (to be implemented in cronogramas-graphql-nextjs)
   │        │
   │        ▼
   └── INSERT INTO fcm_tokens (id_usuario_FK, token)
```

## Manual end-to-end test

The fastest way to validate the worker is end-to-end (no app install needed):

```bash
# 1. Make sure the device token is in the DB
mysql -h 192.168.20.240 -u root -p tomanotas \
  -e "INSERT INTO fcm_tokens (id_usuario_FK, token, platform) VALUES (1, '<real-fcm-token>', 'android') ON DUPLICATE KEY UPDATE updated_at = NOW();"

# 2. Make sure the cronograma is for TODAY
mysql -h 192.168.20.240 -u root -p tomanotas \
  -e "UPDATE cronograma SET fecha = CURDATE() WHERE id_cronograma_PK = 666;"

# 3. Move a task to the CURRENT minute
mysql -h 192.168.20.240 -u root -p tomanotas \
  -e "UPDATE tarea_cronograma SET hora = HOUR(NOW()), minuto = MINUTE(NOW()), notified_at = NULL, estado = 0 WHERE id_tarea_cronograma_PK = 7517;"

# 4. Run the worker
python -m app.worker
```

Expected output:

```
[INFO] fcm-worker: Looking for tasks at 2026-08-08 15:57
[INFO] fcm-worker: Found 1 candidate task(s)
[INFO] fcm-worker: task 7517 notified (msg=projects/mobile-notifications-me/messages/0:178...)
[INFO] fcm-worker: Cycle finished: sent=1 failed=0
```

The Android device should receive the push within 1-2 seconds.

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `Found 0 candidate task(s)` but you have tasks | `cronograma.fecha` is not today | `UPDATE cronograma SET fecha = CURDATE() WHERE id_cronograma_PK = X;` |
| `Found 0 candidate task(s)` | All tasks have `estado = 1` (completed) | Set `estado = 0` |
| `Found 0 candidate task(s)` | All tasks already have `notified_at` set | `UPDATE tarea_cronograma SET notified_at = NULL WHERE id_tarea_cronograma_PK = X;` |
| `Failed to send ... invalid FCM token` | Token is placeholder or expired | Get a real token from `FirebaseMessaging.instance.getToken()` in the app |
| `Failed to send ... UNREGISTERED` | The app was uninstalled; token is dead | Delete the row from `fcm_tokens` |

## Configuration

Configuration is read from one of three sources (see `.env` resolution order):

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_HOST` | yes | `127.0.0.1` | MySQL host (use `127.0.0.1` with `hostNetwork`) |
| `DB_PORT` | no | `3306` | MySQL port |
| `DB_NAME` | yes | `tomanotas` | Database name |
| `DB_USER` | yes | `root` | MySQL user |
| `DB_PASSWORD` | yes | (empty) | MySQL password |
| `GOOGLE_APPLICATION_CREDENTIALS` | yes | `/secrets/firebase-sa.json` | Path to FCM service account JSON |
| `APP_TIMEZONE` | no | `America/Bogota` | Timezone for "now" |

## Secrets and config (k8s)

This project follows the **same pattern as TomaNotas, cronogramas-mcp, and
manejo-finanzas-mcp** in this cluster:

1. **`.env` file** mounted as a file from a shared Secret.
2. **FCM service account JSON** mounted as a file from a separate Secret.

```bash
# 1. Create the shared env Secret (same name as the other projects)
kubectl create secret generic tomanotas-secrets \
  --from-file=.env=./.env \
  -n prod

# 2. Create the FCM credentials Secret
kubectl create secret generic fcm-credentials \
  --from-file=firebase-sa.json=./secrets/firebase-sa.json \
  -n prod
```

The FCM service account JSON is obtained from
[Firebase Console](https://console.firebase.google.com) → Project
`mobile-notifications-me` → ⚙️ Project Settings → **Service Accounts** →
**Generate new private key**.

**Never commit** the Firebase JSON or the `.env` file to git. Both are in
`.gitignore`.

## Build & deploy

```bash
# Build the image
docker build -t aflobaton/cronograms-worker-fcm:0.1.0 .
docker push aflobaton/cronograms-worker-fcm:0.1.0

# Deploy with kustomize
kubectl apply -k deploy/overlays/prod

# Verify
kubectl get cronjob -n prod
kubectl get jobs -n prod --watch
kubectl logs -n prod -l job-name=cronograms-worker-fcm-<timestamp>
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run a specific test file
pytest tests/test_db.py -v

# Run only one test
pytest tests/test_worker.py::test_worker_marks_task_as_notified -v
```

Tests use **SQLite in-memory** (`tests/conftest.py`) with a schema mirroring the
production tables. The worker query is fully parameterized, so it works on both
SQLite and MySQL without changes.

`pytest-mock` keeps tests deterministic — `current_hour_minute_bogota` is patched
in `test_worker.py` so the suite can be run at any wall-clock time.

Current coverage: **93%** (36 tests passing).

## Resource footprint

The CronJob is intentionally **austero**:

- **CPU**: `25m` request / `100m` limit
- **Memory**: `64Mi` request / `128Mi` limit
- **Duration**: ~1–5 seconds per execution (most cycles process 0 tasks)
- **History**: only 3 successful + 5 failed Jobs kept

For the intended load (~20 tasks/day + 30% margin = ~26/day), the worker is
idle >99% of the time and uses only the resources during the few seconds it
runs.

## Security

- Runs as non-root user (`uid=10001`).
- `readOnlyRootFilesystem: true`.
- Drops all Linux capabilities.
- `hostNetwork: true` is required to reach MySQL on the host's `127.0.0.1:3306`.
- The `.env` file and FCM service account JSON are mounted **read-only** from Secrets.

## License

Private project.
