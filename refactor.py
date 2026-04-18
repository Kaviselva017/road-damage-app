import os
import glob
import re

def fix_ai_service():
    with open("backend/app/services/ai_service.py", "r", encoding="utf-8") as f:
        c = f.read()
    c = c.replace("dict[str, object]", "dict[str, Any]")
    if "from typing import" not in c:
        c = "from typing import Any\n" + c
    elif "Any" not in c:
        c = re.sub(r'from typing import (.*)', r'from typing import Any, \1', c, count=1)
    with open("backend/app/services/ai_service.py", "w", encoding="utf-8") as f:
        f.write(c)

def fix_main_py():
    with open("backend/app/main.py", "r", encoding="utf-8") as f:
        c = f.read()
    
    # Remove old events
    c = re.sub(r'@app\.on_event\("startup"\)\s*async def startup_event\(\):\s*.*?(?=\n\n|\Z)', '', c, flags=re.DOTALL)
    c = re.sub(r'@app\.on_event\("shutdown"\)\s*async def shutdown_event\(\):\s*.*?(?=\n\n|\Z)', '', c, flags=re.DOTALL)

    if "lifespan" not in c:
        lifespan = """from contextlib import asynccontextmanager\n\n@asynccontextmanager\nasync def lifespan(app: FastAPI):\n    yield\n\n"""
        c = lifespan + c
        c = c.replace("app = FastAPI(", "app = FastAPI(lifespan=lifespan, ")
        
        with open("backend/app/main.py", "w", encoding="utf-8") as f:
            f.write(c)

def fix_dependencies():
    with open("backend/app/dependencies.py", "r", encoding="utf-8") as f:
        c = f.read()
    
    old_401 = """raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")"""
    new_401 = """raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )"""
    c = c.replace(old_401, new_401)
    
    with open("backend/app/dependencies.py", "w", encoding="utf-8") as f:
        f.write(c)

def fix_db_queries():
    files = glob.glob("backend/app/**/*.py", recursive=True)
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            c = f.read()
        
        orig = c
        
        # Replace simple single-object db.query(Model) -> db.execute(select(Model)).scalars()
        # It's better to just do string replacements for known chains
        # We need to add 'from sqlalchemy import select'
        
        if "db.query(" in c:
            if "from sqlalchemy import" not in c:
                c = "from sqlalchemy import select\n" + c
            elif "select" not in c:
                # Add select
                c = re.sub(r'from sqlalchemy import (.*)', r'from sqlalchemy import select, \1', c, count=1)

            # db.query(Model).filter(...) -> db.execute(select(Model).filter(...)).scalars()
            # We'll use a regex to match db.query(X) up to the next method like .all() or .first()
            # Complex to do accurately with regex, but we know:
            # db.query(A).filter(B) -> db.execute(select(A).filter(B)).scalars()
            
            c = re.sub(r'db\.query\((.*?)\)', r'db.execute(select(\1)).scalars()', c)

            # Note: The above changes db.query(X).filter(Y).all() to db.execute(select(X)).scalars().filter(Y).all()
            # which is INVALID because scalars() doesn't have .filter().
            # So we must fix that! Wait, we shouldn't use naive regex. 
            pass

def fix_fcm_service():
    with open("backend/app/services/fcm_service.py", "r", encoding="utf-8") as f:
        c = f.read()
    
    # Needs guarded imports
    if "except ImportError:" not in c:
        pass # will manually fix

fix_ai_service()
fix_dependencies()
fix_main_py()
# Not running db queries yet to avoid corruption
