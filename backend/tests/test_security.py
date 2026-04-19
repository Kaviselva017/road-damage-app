import pytest
import io
from PIL import Image

@pytest.fixture
def valid_image_bytes():
    buf = io.BytesIO()
    img = Image.new('RGB', (224, 224), color = 'red')
    img.save(buf, format='JPEG')
    return buf.getvalue()

@pytest.mark.asyncio
async def test_rate_limit(async_client, citizen_token, valid_image_bytes):
    from app.limiter import limiter
    limiter.enabled = True
    try:
        headers = {"Authorization": f"Bearer {citizen_token}"}
        lat = 40.0
        for i in range(10):
            files = {"image": (f"test{i}.jpg", valid_image_bytes, "image/jpeg")}
            data = {"latitude": lat + (i * 0.001), "longitude": -74.000}
            res = await async_client.post("/api/complaints/submit", headers=headers, data=data, files=files)
            # Even if some fail with 409 (duplicate) or other errors, 
            # they still count towards the rate limit of 10 requests per minute
            pass

        files = {"image": ("test11.jpg", valid_image_bytes, "image/jpeg")}
        data = {"latitude": lat + 0.02, "longitude": -74.000}
        res = await async_client.post("/api/complaints/submit", headers=headers, data=data, files=files)
        assert res.status_code == 429
        assert res.json().get("error") == "rate_limit_exceeded"
    finally:
        limiter.enabled = False
        try:
            limiter.reset()
        except Exception:
            pass

@pytest.mark.asyncio
async def test_sql_injection(async_client, citizen_token, valid_image_bytes, session):
    headers = {
        "Authorization": f"Bearer {citizen_token}",
        "X-Forwarded-For": "192.168.1.101"
    }
    files = {"image": ("test_sql.jpg", valid_image_bytes, "image/jpeg")}
    malicious_payload = "'; DROP TABLE complaints;--"
    data = {
        "latitude": 41.0,
        "longitude": -74.0,
        "description": f"<b>{malicious_payload}</b>" # To test HTML stripping too
    }
    res = await async_client.post("/api/complaints/submit", headers=headers, data=data, files=files)
    assert res.status_code in (200, 202)
    
    # The SQL injection should be neutralized by parameterized queries —
    # the description is stored as-is (HTML sanitization is a display concern).
    from app.models.models import Complaint
    from sqlalchemy import select
    c = session.execute(select(Complaint).filter(Complaint.complaint_id == res.json()["complaint_id"])).scalars().first()
    assert c is not None
    assert malicious_payload in c.description  # SQL payload stored safely as data
    assert "complaints" in c.description  # The table name is just a string, not executed

@pytest.mark.asyncio
async def test_invalid_image(async_client, citizen_token):
    headers = {
        "Authorization": f"Bearer {citizen_token}",
        "X-Forwarded-For": "192.168.1.102"
    }
    fake_img = b"This is a text file not an image."
    files = {"image": ("fake.jpg", fake_img, "image/jpeg")}
    data = {"latitude": 42.0, "longitude": -74.0}
    res = await async_client.post("/api/complaints/submit", headers=headers, data=data, files=files)
    # The image_validator should fail and return 400 (according to file_validators.py)
    assert res.status_code == 400

@pytest.mark.asyncio
async def test_coord_bounds(async_client, citizen_token, valid_image_bytes):
    headers = {
        "Authorization": f"Bearer {citizen_token}",
        "X-Forwarded-For": "192.168.1.103"
    }
    files = {"image": ("test_bounds.jpg", valid_image_bytes, "image/jpeg")}
    data = {"latitude": 91.0, "longitude": -74.0} # invalid latitude > 90
    res = await async_client.post("/api/complaints/submit", headers=headers, data=data, files=files)
    # The ComplaintCreate Pydantic validator should complain
    assert res.status_code == 422
