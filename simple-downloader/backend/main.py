from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, Any
import httpx, uuid, asyncio, os, re, json
from datetime import datetime
from pathlib import Path

app = FastAPI(title="URL Downloader API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DOWNLOAD_DIR = Path("./downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)
downloads: Dict[str, Dict[str, Any]] = {}

class DownloadRequest(BaseModel):
    url: str

def sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    return filename or "download"

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/downloads")
async def create_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    download_id = str(uuid.uuid4())[:8]
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    download = {"id": download_id, "url": url, "filename": "download.bin", "status": "queued", "progress": 0.0, "downloaded_bytes": 0, "total_bytes": None, "error": None, "created_at": datetime.now().isoformat(), "file_path": None}
    downloads[download_id] = download
    background_tasks.add_task(download_file, download_id)
    return download

@app.get("/api/downloads")
async def list_downloads():
    return {"downloads": list(downloads.values()), "total": len(downloads)}

@app.get("/api/downloads/{download_id}")
async def get_download(download_id: str):
    if download_id not in downloads:
        raise HTTPException(status_code=404, detail="Download not found")
    return downloads[download_id]

async def download_file(download_id: str):
    if download_id not in downloads:
        return
    dl = downloads[download_id]
    try:
        dl["status"] = "downloading"
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            head_resp = await client.head(dl["url"])
            content_length = head_resp.headers.get("content-length")
            if content_length:
                dl["total_bytes"] = int(content_length)
            file_path = DOWNLOAD_DIR / f"{download_id}_download.bin"
            dl["file_path"] = str(file_path)
            downloaded = 0
            async with client.stream("GET", dl["url"]) as resp:
                with open(file_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        dl["downloaded_bytes"] = downloaded
                        if dl["total_bytes"]:
                            dl["progress"] = min(100.0, (downloaded / dl["total_bytes"]) * 100)
        dl["status"] = "completed"
        dl["progress"] = 100.0
    except Exception as e:
        dl["status"] = "failed"
        dl["error"] = str(e)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
