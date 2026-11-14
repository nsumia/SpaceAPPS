"""Minimal FastAPI app (Stage 4 adds the lake endpoints). Run: .venv/bin/uvicorn backend.api.main:app"""
from fastapi import FastAPI

app = FastAPI(title="Lake Loss Detective API", version="0.2.0")


@app.get("/api/health")
def health():
    return {"status": "ok"}
