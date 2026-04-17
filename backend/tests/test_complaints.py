import pytest

@pytest.mark.asyncio
async def test_submit_complaint_auth(async_client, citizen_token, dummy_image):
    headers = {"Authorization": f"Bearer {citizen_token}"}
    files = {"image": ("test.jpg", dummy_image, "image/jpeg")}
    data = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "address": "123 Main St",
    }
    
    res = await async_client.post(
        "/api/complaints/submit",
        headers=headers,
        data=data,
        files=files
    )
    assert res.status_code == 200
    res_data = res.json()
    assert "id" in res_data or "complaint_id" in res_data

@pytest.mark.asyncio
async def test_submit_complaint_no_auth(async_client, dummy_image):
    files = {"image": ("test.jpg", dummy_image, "image/jpeg")}
    data = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "address": "123 Main St",
    }
    res = await async_client.post("/api/complaints/submit", data=data, files=files)
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_get_my_complaints(async_client, citizen_token, dummy_image):
    headers = {"Authorization": f"Bearer {citizen_token}"}
    files = {"image": ("test.jpg", dummy_image, "image/jpeg")}
    await async_client.post(
        "/api/complaints/submit",
        headers=headers,
        data={"latitude": 10.0, "longitude": 10.0},
        files=files
    )

    res = await async_client.get("/api/complaints/my", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

@pytest.mark.asyncio
async def test_officer_list_all(async_client, officer_token):
    headers = {"Authorization": f"Bearer {officer_token}"}
    res = await async_client.get("/api/complaints/", headers=headers)
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_citizen_list_all(async_client, citizen_token):
    headers = {"Authorization": f"Bearer {citizen_token}"}
    res = await async_client.get("/api/complaints/", headers=headers)
    assert res.status_code in [401, 403]

@pytest.mark.asyncio
async def test_officer_update_status(async_client, officer_token, citizen_token, dummy_image):
    headers_cit = {"Authorization": f"Bearer {citizen_token}"}
    files = {"image": ("test.jpg", dummy_image, "image/jpeg")}
    data = {
        "latitude": 40.0,
        "longitude": -74.0,
        "address": "Test"
    }
    res = await async_client.post("/api/complaints/submit", headers=headers_cit, data=data, files=files)
    assert res.status_code == 200
    
    complaint_data = res.json()
    complaint_id = complaint_data.get("complaint_id") or complaint_data.get("id")
    
    headers_off = {"Authorization": f"Bearer {officer_token}"}
    res_update = await async_client.patch(
        f"/api/complaints/{complaint_id}/status",
        headers=headers_off,
        json={"status": "in_progress", "officer_notes": "Checking"}
    )
    assert res_update.status_code == 200

@pytest.mark.asyncio
async def test_citizen_update_status(async_client, citizen_token):
    headers_cit = {"Authorization": f"Bearer {citizen_token}"}
    res = await async_client.patch(
        "/api/complaints/test-id/status",
        headers=headers_cit,
        json={"status": "in_progress"}
    )
    assert res.status_code in [401, 403]
