import json
import time
import httpx

BASE = "http://127.0.0.1:8001"
URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"

with httpx.Client(base_url=BASE, timeout=30.0) as client:
    created = client.post("/api/downloads", json={"url": URL})
    download_id = created.json()["id"]
    events = []
    with client.stream("GET", f"/api/downloads/{download_id}/events", headers={"Accept": "text/event-stream"}) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                events.append(event)
                if event.get("terminal") or event.get("status") in {"completed", "failed", "cancelled"}:
                    break
    for _ in range(20):
        current = client.get(f"/api/downloads/{download_id}").json()
        if current["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.25)
    deleted = client.delete(f"/api/downloads/{download_id}")
    print(json.dumps({
        "create_status": created.status_code,
        "download_id": download_id,
        "sse_content_type": response.headers.get("content-type"),
        "events": events,
        "final_status": current["status"],
        "delete_status": deleted.status_code,
    }, indent=2))
