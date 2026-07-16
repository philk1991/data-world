"""Verano personalisation API (Layer 5 — serving).

A small FastAPI app that reads the precomputed ml.* tables read-only and exposes
one endpoint per consumer channel:

  POST /search/rerank                         — search-engine personalisation at query time
  GET  /website/recommendations/{customer_id} — PDP / homepage pull (+ cold-start fallback)
  GET  /email/batch-export                    — consent-gated campaign export

Run: task verano:serve   → http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI

from routers import email, search, website

app = FastAPI(
    title="Verano Personalisation API",
    description="Serving layer over the precomputed recommendation ml.* tables.",
    version="1.0.0",
)
app.include_router(search.router)
app.include_router(website.router)
app.include_router(email.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": "Verano Personalisation API",
        "docs": "/docs",
        "endpoints": [
            "POST /search/rerank",
            "GET /website/recommendations/{customer_id}?slot=homepage|pdp&product_id=",
            "GET /email/batch-export?min_decile=1&limit=100",
        ],
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
