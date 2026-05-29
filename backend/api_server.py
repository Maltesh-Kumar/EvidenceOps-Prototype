from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .workflow_service import WorkflowService

ROOT = Path(__file__).resolve().parent.parent
service = WorkflowService()

app = FastAPI(title="EvidenceOps Assistant Prototype")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class VendorCreate(BaseModel):
    name: str
    category: str
    owner: str
    reviewer: str
    stage: str = "Pre-onboarding"
    dueDate: str
    riskAnswers: dict = {}
    templateId: str | None = None
    actor: str | None = None


class EvidenceSubmit(BaseModel):
    fileName: str
    validUntil: str | None = None
    notes: str = ""
    submittedBy: str | None = None
    actor: str | None = None


class EvidenceDecision(BaseModel):
    decision: str
    reason: str = ""
    createIssue: bool = True
    actor: str | None = None


class StatusUpdate(BaseModel):
    status: str
    actor: str | None = None


class VendorReject(BaseModel):
    reason: str
    actor: str | None = None


@app.get("/api/state")
def get_state():
    return service.state()


@app.post("/api/reset")
def reset():
    return service.reset()


@app.post("/api/vendors")
def create_vendor(payload: VendorCreate):
    return service.create_vendor(payload.model_dump())


@app.post("/api/vendors/{vendor_id}/evidence/{evidence_id}/submit")
def submit_evidence(vendor_id: str, evidence_id: str, payload: EvidenceSubmit):
    return service.submit_evidence(vendor_id, evidence_id, payload.model_dump())


@app.post("/api/vendors/{vendor_id}/evidence/{evidence_id}/upload")
def upload_evidence_file(
    vendor_id: str,
    evidence_id: str,
    file: UploadFile = File(...),
    validUntil: str | None = Form(None),
    notes: str = Form(""),
    actor: str | None = Form(None),
):
    return service.upload_evidence_file(vendor_id, evidence_id, file, validUntil, notes, actor)


@app.post("/api/vendors/{vendor_id}/evidence/{evidence_id}/decision")
def decide_evidence(vendor_id: str, evidence_id: str, payload: EvidenceDecision):
    return service.decide_evidence(vendor_id, evidence_id, payload.model_dump())


@app.post("/api/vendors/{vendor_id}/issues/{issue_id}")
def update_issue(vendor_id: str, issue_id: str, payload: StatusUpdate):
    return service.update_issue_status(vendor_id, issue_id, payload.status, payload.actor)


@app.post("/api/vendors/{vendor_id}/followups/{followup_id}")
def update_followup(vendor_id: str, followup_id: str, payload: StatusUpdate):
    return service.update_followup_status(vendor_id, followup_id, payload.status, payload.actor)


@app.post("/api/vendors/{vendor_id}/reject")
def reject_vendor(vendor_id: str, payload: VendorReject):
    return service.reject_vendor(vendor_id, payload.reason, payload.actor)


app.mount("/", StaticFiles(directory=ROOT, html=True), name="static")
