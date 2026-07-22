import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from backend.api.routes_applications import router as applications_router
from backend.db.session import init_db

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.temporal_client = await Client.connect(
        TEMPORAL_ADDRESS, data_converter=pydantic_data_converter
    )
    yield


app = FastAPI(title="Loan Disbursement API", lifespan=lifespan)
app.include_router(applications_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
