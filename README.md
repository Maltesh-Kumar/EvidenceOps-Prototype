# EvidenceOps Prototype

EvidenceOps Assistant is a working MVP prototype for vendor security evidence review.

It demonstrates:

- Vendor intake and risk tiering
- Evidence requirement templates
- Evidence submission and AI-assisted review simulation
- Reviewer decisions and risk issue creation
- Follow-up tracking
- Vendor status rollups
- Audit-ready activity history
- SQLite-backed durable storage
- Local evidence file storage for uploaded files
- Persona-based audit actions

## Run locally

```powershell
pip install -r requirements.txt
python -m uvicorn backend.api_server:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/
```

The app creates its local database at:

```text
data/evidenceops.sqlite
```

Uploaded evidence files are stored under:

```text
uploads/
```
