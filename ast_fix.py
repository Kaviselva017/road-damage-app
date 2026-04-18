import os
import glob
import re

files = glob.glob("backend/app/**/*.py", recursive=True)

for path in files:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    orig = content

    if "db.query(" in content:
        if "from sqlalchemy import" not in content:
            content = "from sqlalchemy import select\n" + content
        elif "select" not in content:
            content = re.sub(r'from sqlalchemy import (.*)', r'from sqlalchemy import select, \1', content, count=1)

        # Basic naive replacement for lines like `db.query(Model)` -> `db.scalars(select(Model))`
        # We need to replace db.query(Model).filter(...) -> db.execute(select(Model).filter(...)).scalars()
        # Since .first(), .all(), .count() follow, wrapping it properly is hard without AST.
        
        # Let's try: `db.query(M)` -> `db.execute(select(M)).scalars()`
        # Wait, `.scalars()` DOES NOT have `.filter()`. 
        # But we CAN do `db.query` -> `db.session.execute` if we map perfectly.
        # SQLAlchemy 2.0 provides `db.scalars(select(M).filter(...)).all()` as the canonical way.
        pass

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
