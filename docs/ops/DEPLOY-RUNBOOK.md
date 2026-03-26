# Deployment Runbook

## Prerequisites

- GCE access: `gcloud compute ssh instance-20260315-141112 --zone us-central1-f`
- Git repo access to `seapex-ai/seabay-internal`
- Local repository at `/Users/moxiongjie/SeaBay/Seabayai/`

## Standard Deployment Flow

### 1. Local: Prepare and Verify

```bash
cd /Users/moxiongjie/SeaBay/Seabayai

# Verify lint
python3 -m ruff check backend/

# Run tests
cd backend && pytest tests/ -v --ignore=tests/integration && cd ..

# Verify git status
git status  # must be clean
git log --oneline -3  # confirm HEAD
```

### 2. Local: Commit and Push

```bash
git add <files>
git commit -m "fix: description"
git push origin main
```

### 3. Upload to Server (git bundle method)

```bash
# Create bundle
git bundle create /tmp/seabay-main.bundle main

# Upload
CLOUDSDK_PYTHON=~/.local/miniforge-gcloud/bin/python3.13 \
  ~/bin/gcloud compute scp /tmp/seabay-main.bundle \
  instance-20260315-141112:/tmp/seabay-main.bundle \
  --zone us-central1-f --project gen-lang-client-0723744794

# Apply on server
CLOUDSDK_PYTHON=~/.local/miniforge-gcloud/bin/python3.13 \
  ~/bin/gcloud compute ssh instance-20260315-141112 \
  --zone us-central1-f --project gen-lang-client-0723744794 \
  --command "cd /opt/seabay && \
    git fetch /tmp/seabay-main.bundle main:refs/remotes/origin/main && \
    git reset --hard origin/main"
```

### 4. Server: Rebuild and Restart

```bash
# Rebuild changed services (api, mcp-edge, or both)
docker compose -f docker-compose.prod.yml up -d --build api mcp-edge

# Wait for health
sleep 15
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

### 5. Verify

```bash
# Health checks
curl -s http://localhost:8000/v1/health
curl -s http://localhost:8100/health

# Docker status
docker ps  # all 4 healthy

# Git alignment
git log --oneline -1  # matches local HEAD
git status --short    # clean (only .env and scripts)
```

### 6. Sync Public Repo (if needed)

```bash
# From local
git fetch public
git checkout -b sync-fix public/main
git cherry-pick <commit>
git push public sync-fix:main
git checkout main && git branch -d sync-fix
```

## Emergency Hotfix

For critical production issues:

1. Fix locally, test, commit
2. Upload directly via `scp` (tar method for single files):
   ```bash
   tar czf /tmp/fix.tar.gz <changed-files>
   gcloud compute scp /tmp/fix.tar.gz server:/tmp/
   # On server: cd /opt/seabay && tar xzf /tmp/fix.tar.gz
   ```
3. Rebuild affected container
4. Verify health
5. Backfill: push to GitHub after verification

## Checklist

- [ ] Local lint clean
- [ ] Local tests pass
- [ ] Git committed and pushed to internal
- [ ] Server updated (git bundle or scp)
- [ ] Containers rebuilt and healthy
- [ ] Health checks pass (API + MCP Edge)
- [ ] Public repo synced (if applicable)
- [ ] Git status clean on server
