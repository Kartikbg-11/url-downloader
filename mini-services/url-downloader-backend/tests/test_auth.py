"""Integration tests for login sessions and per-user download isolation."""

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.download import DownloadStatus
from app.storage.download_repository import DownloadRecord, get_repository


def test_protected_endpoint_requires_login():
    with TestClient(app) as client:
        response = client.get("/api/downloads")

    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "AUTH_REQUIRED"


def test_invalid_credentials_are_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "user1", "password": "wrong-password"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_me_and_logout_session_flow():
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "user1", "password": "User1@123"},
        )
        assert login.status_code == 200
        assert login.json() == {"username": "user1"}
        assert "HttpOnly" in login.headers["set-cookie"]

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json() == {"username": "user1"}

        downloads = client.get("/api/downloads")
        assert downloads.status_code == 200

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 204
        assert client.get("/api/auth/me").status_code == 401


def test_users_cannot_read_each_others_downloads():
    repository = get_repository()
    download_id = str(uuid4())
    record = DownloadRecord(
        id=download_id,
        owner="user1",
        url="https://example.com/file.zip",
        filename="file.zip",
        status=DownloadStatus.FAILED,
    )
    asyncio.run(repository.create(record))

    try:
        with TestClient(app) as user1_client, TestClient(app) as user2_client:
            assert user1_client.post(
                "/api/auth/login",
                json={"username": "user1", "password": "User1@123"},
            ).status_code == 200
            assert user2_client.post(
                "/api/auth/login",
                json={"username": "user2", "password": "User2@123"},
            ).status_code == 200

            owner_response = user1_client.get(f"/api/downloads/{download_id}")
            assert owner_response.status_code == 200
            assert owner_response.json()["owner"] == "user1"

            other_user_response = user2_client.get(f"/api/downloads/{download_id}")
            assert other_user_response.status_code == 404

            user2_list = user2_client.get("/api/downloads").json()
            assert all(item["id"] != download_id for item in user2_list["downloads"])
    finally:
        asyncio.run(repository.delete(download_id))
