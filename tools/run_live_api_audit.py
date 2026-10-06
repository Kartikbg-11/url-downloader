import json
import time
from datetime import datetime, timezone

import httpx


BASE = "http://127.0.0.1:8001"
MISSING_ID = "00000000-0000-0000-0000-000000000000"
DIRECT_PDF = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
MEDIA_URL = "https://youtu.be/RLzC55ai0eo"


def compact_body(response):
    content_type = response.headers.get("content-type", "")
    if "json" in content_type:
        try:
            return response.json()
        except Exception:
            pass
    text = response.text
    return text[:500] + ("..." if len(text) > 500 else "")


def record(results, name, response, started):
    results.append({
        "name": name,
        "method": response.request.method,
        "path": response.request.url.raw_path.decode("utf-8"),
        "status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "body": compact_body(response),
    })


def call(client, results, name, method, path, **kwargs):
    started = time.perf_counter()
    response = client.request(method, path, **kwargs)
    record(results, name, response, started)
    return response


def main():
    results = []
    with httpx.Client(base_url=BASE, timeout=45.0, follow_redirects=True) as client:
        call(client, results, "API information", "GET", "/")
        call(client, results, "Health check", "GET", "/api/health")
        call(client, results, "OpenAPI schema", "GET", "/openapi.json")
        call(client, results, "Swagger UI", "GET", "/docs")
        call(client, results, "ReDoc UI", "GET", "/redoc")
        call(client, results, "Frontend sample API", "GET", "http://127.0.0.1:3000/api")

        call(client, results, "List downloads", "GET", "/api/downloads?limit=50&offset=0")
        call(client, results, "List invalid status", "GET", "/api/downloads?status=unknown")
        call(client, results, "List invalid lower limit", "GET", "/api/downloads?limit=0")
        call(client, results, "List invalid upper limit", "GET", "/api/downloads?limit=101")
        call(client, results, "List invalid offset", "GET", "/api/downloads?offset=-1")

        call(client, results, "Get missing download", "GET", f"/api/downloads/{MISSING_ID}")
        call(client, results, "SSE missing download", "GET", f"/api/downloads/{MISSING_ID}/events")
        call(client, results, "Get missing file", "GET", f"/api/downloads/{MISSING_ID}/file")
        call(client, results, "Cancel missing download", "POST", f"/api/downloads/{MISSING_ID}/cancel")
        call(client, results, "Delete missing download", "DELETE", f"/api/downloads/{MISSING_ID}")

        call(client, results, "Create missing body field", "POST", "/api/downloads", json={})
        call(client, results, "Create extra body field", "POST", "/api/downloads", json={"url": DIRECT_PDF, "unexpected": True})
        call(client, results, "Create invalid media type", "POST", "/api/downloads", json={"url": MEDIA_URL, "format_id": "134", "media_type": "text"})
        call(client, results, "Inspect media invalid URL", "POST", "/api/downloads/media-info", json={"url": "not-a-url"})

        try:
            call(client, results, "Inspect media formats", "POST", "/api/downloads/media-info", json={"url": MEDIA_URL})
        except Exception as exc:
            results.append({"name": "Inspect media formats", "transport_error": str(exc)})

        created = call(client, results, "Create direct PDF download", "POST", "/api/downloads", json={"url": DIRECT_PDF})
        download_id = created.json().get("id") if created.status_code == 202 else None
        if download_id:
            final = None
            for _ in range(30):
                time.sleep(0.5)
                response = call(client, results, "Poll direct PDF status", "GET", f"/api/downloads/{download_id}")
                final = response.json()
                if final.get("status") in {"completed", "failed", "cancelled"}:
                    break

            if final and final.get("status") == "completed":
                response = client.get(f"/api/downloads/{download_id}/file")
                results.append({
                    "name": "Retrieve completed file",
                    "method": "GET",
                    "path": f"/api/downloads/{download_id}/file",
                    "status": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "content_disposition": response.headers.get("content-disposition"),
                    "bytes": len(response.content),
                })

            call(client, results, "Cancel terminal download", "POST", f"/api/downloads/{download_id}/cancel")
            call(client, results, "Delete terminal download", "DELETE", f"/api/downloads/{download_id}")
            call(client, results, "Confirm deleted download", "GET", f"/api/downloads/{download_id}")

        queued = call(client, results, "Create job for cancellation", "POST", "/api/downloads", json={"url": "https://example.com/file.pdf"})
        cancel_id = queued.json().get("id") if queued.status_code == 202 else None
        if cancel_id:
            call(client, results, "Cancel active download", "POST", f"/api/downloads/{cancel_id}/cancel")
            time.sleep(0.2)
            call(client, results, "Get cancelled download", "GET", f"/api/downloads/{cancel_id}")
            call(client, results, "File for cancelled download", "GET", f"/api/downloads/{cancel_id}/file")
            call(client, results, "Delete cancelled download", "DELETE", f"/api/downloads/{cancel_id}")

    payload = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "results": results,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
