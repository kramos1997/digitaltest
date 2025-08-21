#!/usr/bin/env python3
"""Main entry point for ClarityDesk FastAPI application."""

import os
import sys
import uvicorn
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir.parent))

if __name__ == "__main__":
    # Set development environment
    os.environ.setdefault("ENVIRONMENT", "development")
    
    # Run the FastAPI application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        reload_dirs=["app"],
        log_level="info"
    )