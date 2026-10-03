"""FastAPI application entrypoint and server definition."""
import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.models.db import init_db
from src.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise database schema upon application startup
    init_db()
    yield


app = FastAPI(
    title="Experience Recorder API",
    description="End-to-End Experience Recorder for Capturing and Localising Intermittent Service Degradation in Branch-Based Financial Organisations",
    version="1.0.0",
    lifespan=lifespan
)

# Allow CORS for local Streamlit dashboard and testing tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router, prefix="/api/v1")



@app.get("/")
def root_redirect():
    """Root redirect to OpenAPI documentation."""
    return {
        "project": "End-to-End Experience Recorder",
        "status": "online",
        "docs_url": "/docs",
        "api_v1": "/api/v1"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=True)
