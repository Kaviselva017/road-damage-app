import os
import glob
import re

for filepath in glob.glob("backend/app/**/*.py", recursive=True):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    orig = content
    # Fix == True -> .is_(True)
    content = re.sub(r'([A-Za-z0-9_.]+)\s*==\s*True', r'\1.is_(True)', content)
    # Fix == False -> .is_(False)
    content = re.sub(r'([A-Za-z0-9_.]+)\s*==\s*False', r'\1.is_(False)', content)
    # Revert if it's purely a python bool check (not SQLAlchemy) but usually in these repos `is_admin == False` is in `filter(...)`.
    
    # Let's fix E402 by manually finding all module level imports that are below line 30 and moving them up?
    # No, it's safer to just use isort but isort doesn't move them.
    # Actually wait: `from app.dependencies import ...` inside a function is NOT a module level import!
    # The E402 is because the file had a function, then a route definition, then an import!
    # Let's just fix E402 using ruff somehow, or a script. Let's fix E712 first.
    if orig != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
