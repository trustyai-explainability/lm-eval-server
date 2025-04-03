
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import importlib.metadata

# Endpoint routers
from src.lm_eval_harness_server import router as eval_router

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LM Evaluation Harness Service API",
    version=importlib.metadata.version("lm-eval-server"),
    description="LM Evaluation Harness Service API",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    eval_router,
    tags=["Eval"],
)

if __name__ == "__main__":
    uvicorn.run(app=app, host="0.0.0.0", port=8080)