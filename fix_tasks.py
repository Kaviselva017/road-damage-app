import re

# 1. AI Service
with open("backend/app/services/ai_service.py", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("dict[str, object]", "dict[str, Any]")
if "from typing import" not in c:
    c = c.replace("import typing", "from typing import Any\nimport typing")
elif "Any" not in c for _ in ["dict[str, Any]"]:
    c = re.sub(r'from typing import (.*)', r'from typing import Any, \1', c, count=1)
with open("backend/app/services/ai_service.py", "w", encoding="utf-8") as f:
    f.write(c)

# 2. Main
with open("backend/app/main.py", "r", encoding="utf-8") as f:
    c = f.read()

lifespan_str = """from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
"""
c = re.sub(r'@app\.on_event\("startup"\)\s*async def startup_event\(\):\s*.*?(?=\n\n|\Z)', '', c, flags=re.DOTALL)
c = c.replace('app = FastAPI(', f'{lifespan_str}\napp = FastAPI(lifespan=lifespan, ')
with open("backend/app/main.py", "w", encoding="utf-8") as f:
    f.write(c)
