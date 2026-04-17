import pytest

@pytest.mark.asyncio
async def test_register_citizen(async_client):
    res = await async_client.post("/api/auth/register", json={
        "name": "Citizen One",
        "email": "c1@test.com",
        "phone": "111",
        "password": "pass"
    })
    assert res.status_code == 201

@pytest.mark.asyncio
async def test_register_duplicate(async_client):
    data = {
        "name": "Citizen Two",
        "email": "c2@test.com",
        "phone": "222",
        "password": "pass"
    }
    await async_client.post("/api/auth/register", json=data)
    res = await async_client.post("/api/auth/register", json=data)
    assert res.status_code == 400

@pytest.mark.asyncio
async def test_login_correct(async_client):
    await async_client.post("/api/auth/register", json={
        "name": "Citizen Login",
        "email": "login@test.com",
        "phone": "333",
        "password": "correct"
    })
    res = await async_client.post("/api/auth/login", json={
        "email": "login@test.com",
        "password": "correct"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()

@pytest.mark.asyncio
async def test_login_wrong_password(async_client):
    await async_client.post("/api/auth/register", json={
        "name": "Citizen Wrong",
        "email": "wrong@test.com",
        "phone": "444",
        "password": "right"
    })
    res = await async_client.post("/api/auth/login", json={
        "email": "wrong@test.com",
        "password": "wrong"
    })
    assert res.status_code == 401
