import io
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db


# ── Rate limiter: completely disable during tests ──────────────────────────────
@pytest.fixture(autouse=True)
def _disable_rate_limiter(monkeypatch):
    from app.limiter import limiter

    monkeypatch.setattr(limiter, "enabled", False, raising=False)
    try:
        limiter.reset()
    except Exception:
        pass
    yield
    try:
        limiter.reset()
    except Exception:
        pass


# ── APScheduler: prevent start during test collection ─────────────────────────
@pytest.fixture(autouse=True, scope="session")
def _disable_scheduler():
    """Prevent APScheduler from starting during tests."""
    import app.main as main_mod

    main_mod._SCHEDULER_STARTED = True  # signal already started
    yield


# ── In-memory SQLite for testing ───────────────────────────────────────────────
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

from sqlalchemy.ext.compiler import compiles
from geoalchemy2.types import Geography


@compiles(Geography, "sqlite")
def compile_geography(type_, compiler, **kw):
    type_.spatial_index = False
    type_.management = False
    return "TEXT"


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def register_sqlite_geo_stubs(dbapi_conn, connection_record=None):
    """Register no-op stubs for every PostGIS/GeoAlchemy2 function SQLite lacks."""
    noop1 = lambda x: x
    noop2 = lambda x, y: x
    for fn_name in (
        "AsBinary", "AsEWKB", "ST_GeomFromEWKT", "ST_GeogFromText",
        "ST_AsText", "ST_AsEWKT", "ST_AsBinary", "ST_AsEWKB",
        "ST_GeomFromText", "ST_GeomFromWKB",
    ):
        dbapi_conn.create_function(fn_name, 1, noop1)
    for fn_name in ("ST_SetSRID", "ST_DWithin"):
        dbapi_conn.create_function(fn_name, 2, noop2)
    # ST_MakePoint(lng, lat) → just return None (we never read location in SQLite)
    dbapi_conn.create_function("ST_MakePoint", 2, lambda x, y: None)
    # 3-arg variants
    dbapi_conn.create_function("ST_DWithin", 3, lambda x, y, z: False)
    dbapi_conn.create_function("ST_SetSRID", 2, lambda x, y: x)


sa_event.listen(engine, "connect", register_sqlite_geo_stubs)


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session(session):
    """Alias used by auth/phone tests."""
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(session):
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Patch SessionLocal everywhere it's used directly (background tasks)
    # so they use the test engine with GeoAlchemy2 stubs instead of production.
    import app.database as _db_mod
    import app.api.complaints as _complaints_mod

    orig_sl = _db_mod.SessionLocal
    _db_mod.SessionLocal = TestingSessionLocal
    _complaints_mod.SessionLocal = TestingSessionLocal

    yield app

    _db_mod.SessionLocal = orig_sl
    _complaints_mod.SessionLocal = orig_sl
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def async_client(client):
    transport = ASGITransport(app=client)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ── Google-auth era fixtures ──────────────────────────────────────────

@pytest.fixture
def test_user(db_session):
    """A user with google_sub but NO phone_number (new sign-up state)."""
    from app.models.models import User

    user = User(
        name="Test User",
        email="testuser@gmail.com",
        google_sub="google_test_123",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_user(db_session):
    from app.models.models import User

    user = User(
        name="Second User",
        email="second@gmail.com",
        google_sub="google_second_456",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_no_phone(db_session):
    """User with google_sub but explicitly no phone_number."""
    from app.models.models import User

    user = User(
        name="No Phone User",
        email="nophone@gmail.com",
        google_sub="google_nophone_789",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(db_session):
    """Returns a callable that creates a Bearer header with a valid access token for any user."""
    from app.api.auth import _make_access_token

    def _make(user):
        token = _make_access_token(user.id, user.google_sub or "")
        return {"Authorization": f"Bearer {token}"}

    return _make


# ── Legacy fixtures (async) ───────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def citizen_token(db_session, test_user):
    """Legacy fixture — kept for backward compat with older tests."""
    from app.api.auth import _make_access_token

    # Ensure user has a phone number so they pass require_phone_complete
    test_user.phone_number = "+919999988888"
    db_session.commit()
    return _make_access_token(test_user.id, test_user.google_sub or "")


@pytest_asyncio.fixture(scope="function")
async def officer_token(async_client, session):
    from app.models.models import FieldOfficer
    from app.services.auth_service import create_access_token, hash_password

    # Try to find existing officer to avoid UNIQUE constraint failed if we're reusing the session
    officer = session.query(FieldOfficer).filter_by(email="officer@test.com").first()
    if not officer:
        officer = FieldOfficer(
            name="Test Officer",
            email="officer@test.com",
            phone_number="0987654321",
            hashed_password=hash_password("password123"),
            zone="North",
            is_admin=True,
            is_active=True,
        )
        session.add(officer)
        session.commit()
        session.refresh(officer)

    # Use create_access_token to ensure logic matches what decode_token expects
    token = create_access_token({"sub": str(officer.id), "role": "admin"})
    return token


@pytest.fixture
def dummy_image():
    """Generate a real valid JPEG in-memory using Pillow."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf.read()
