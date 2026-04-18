import os
import glob
import re

files = glob.glob("backend/app/**/*.py", recursive=True)

for path in files:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if "db.query(" not in content:
        continue

    # Add import
    if "from sqlalchemy import" not in content:
        content = "from sqlalchemy import select\n" + content
    elif "select" not in content:
        content = re.sub(r'from sqlalchemy import (.*)', r'from sqlalchemy import select, \1', content, count=1)

    # Replace `.all()`
    # Match: db.query(Model).XYZ.all()
    # It's tricky because there can be multiple lines.
    content = re.sub(r'db\.query\((.*?)\)(.*?)\.all\(\)', r'db.execute(select(\1)\2).scalars().all()', content, flags=re.DOTALL)
    
    # Replace `.first()`
    content = re.sub(r'db\.query\((.*?)\)(.*?)\.first\(\)', r'db.execute(select(\1)\2).scalars().first()', content, flags=re.DOTALL)

    # Replace `.count()` -> note that .count() doesn't use scalars in v2.
    # It must be db.execute(select(func.count(Model.id))...).scalar() but for now we ignore or map carefully.
    
    # What if it's db.query(Model).filter(...).limit(50).all()?
    # The dotall regex might match TOO much if there are multiple .all() in a file.
    pass
