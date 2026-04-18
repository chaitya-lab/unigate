#!/usr/bin/env python
"""Minimal uvicorn test."""
import uvicorn

app = uvicorn.App("uvicorn:App", host="0.0.0.0", port=8080, log_level="info")
uvicorn.run(app)
