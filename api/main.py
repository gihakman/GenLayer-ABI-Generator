"""FastAPI web service for GenLayer ABI Generator."""

import sys
from pathlib import Path

# Add parent directory to path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from genlayer_abi.parser import extract_abi, abi_to_dict
from genlayer_abi.generator import (
    generate_full_ts_package,
    generate_genlayer_js_wrapper,
    generate_ts_abi,
    generate_react_hooks,
)

app = FastAPI(
    title="GenLayer ABI Generator",
    description="Type-Safe Frontend Toolkit for GenLayer Intelligent Contracts",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ExtractAbiRequest(BaseModel):
    contract_source: str = Field(..., description="Python source code of the GenLayer contract")
    contract_address: str = Field(default="0x0000...", description="Deployed contract address")


class ExtractAbiResponse(BaseModel):
    contract_name: str
    methods: list[dict]


class GenerateTsRequest(BaseModel):
    contract_source: str = Field(..., description="Python source code")
    contract_address: str = Field(default="0x0000...")


class GenerateTsResponse(BaseModel):
    files: dict[str, str]


@app.get("/")
def root():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"status": "ok", "service": "GenLayer ABI Generator v0.1.0"}


@app.post("/api/extract-abi", response_model=ExtractAbiResponse)
def extract_abi_endpoint(req: ExtractAbiRequest) -> ExtractAbiResponse:
    try:
        abi = extract_abi(req.contract_source)
        return ExtractAbiResponse(**abi_to_dict(abi))
    except (ValueError, SyntaxError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-ts", response_model=GenerateTsResponse)
def generate_ts_endpoint(req: GenerateTsRequest) -> GenerateTsResponse:
    try:
        abi = extract_abi(req.contract_source)
        files = generate_full_ts_package(abi, req.contract_address)
        wrapper = generate_genlayer_js_wrapper(abi, req.contract_address)
        files[f"{abi.contract_name}Wrapper.ts"] = wrapper
        return GenerateTsResponse(files=files)
    except (ValueError, SyntaxError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-abi-json")
def generate_abi_json_endpoint(req: ExtractAbiRequest) -> dict:
    try:
        abi = extract_abi(req.contract_source)
        return abi_to_dict(abi)
    except (ValueError, SyntaxError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
