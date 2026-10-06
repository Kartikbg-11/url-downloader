import json
import time
import httpx

BASE = "http://127.0.0.1:8001"
CASES = [
    ("empty URL", ""),
    ("unsupported FTP scheme", "ftp://example.com/file.pdf"),
    ("loopback SSRF target", "http://127.0.0.1/private.pdf"),
    ("HTML page instead of file", "https://example.com/"),
]

results = []
with httpx.Client(base_url=BASE, timeout=30.0) as client:
    for name, url in CASES:
        created = client.post("/api/downloads", json={"url": url})
        item = {"case": name, "submitted_url": url, "create_status": created.status_code, "create_body": created.json()}
        if created.status_code == 202:
            download_id = created.json()["id"]
            for _ in range(40):
                time.sleep(0.1)
                status = client.get(f"/api/downloads/{download_id}")
                body = status.json()
                if body.get("status") in {"completed", "failed", "cancelled"}:
                    break
            item["terminal_status"] = body.get("status")
            item["terminal_error"] = body.get("error")
            item["delete_status"] = client.delete(f"/api/downloads/{download_id}").status_code
        results.append(item)

print(json.dumps(results, indent=2))
