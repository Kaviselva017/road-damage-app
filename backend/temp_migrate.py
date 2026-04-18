import glob
import re

files = glob.glob("backend/app/**/*.py", recursive=True)

def find_closing_paren(s, start):
    count = 0
    for i in range(start, len(s)):
        if s[i] == '(':
            count += 1
        elif s[i] == ')':
            count -= 1
            if count == 0:
                return i
    return -1

# We will match "db.query(" and then find its closing parenthesis.
# We replace "db.query(" with "db.execute(select("
# Wait, if we replace db.query(M).filter(X).all()
# We want db.execute(select(M).filter(X)).scalars().all()
# That means the close paren of db.execute matching the open paren of db.execute( 
# should be right before the `.scalars()`. Which means right before `.all()`, `.first()`, or at the end.

# This means the expression from AFTER db.query(M) up to `.all()` or `.first()` or `.count()` must be wrapped in db.execute(select(M)...)
# But what if there is no `.all()`, just db.query(M) passing a query object around?

def migrate(c):
    # Add imports
    if "db.query(" not in c:
        return c
    if "from sqlalchemy import select" not in c:
        if "from sqlalchemy import" in c:
            c = re.sub(r"from sqlalchemy import (.*)", r"from sqlalchemy import select, \1", c, count=1)
        else:
            c = "from sqlalchemy import select\n" + c

    # Since there are small number of files with specific chains, we can just replace the standard ones easily via regex if we do it sequentially.
    # Pattern: db.query(MODEL).WHATEVER... .all()  | .first() | .count()
    # It always ends in .all() or .first() or .scalar() or .count() or .update()

    # To be extremely foolproof, let's use a very basic regex that handles spaces around chains.
    # We look for: db.query( X )( Y ).Z()
    # Instead: we replace `db.query` with `db.execute(select`
    # and then the `scalars().first()` or `scalars().all()` string.
    # WAIT! There is a simple pattern:
    # 1. replace `db.query(` with `db.execute(select(`
    # This creates: `db.execute(select(User).filter(...).all()`
    # We then look for `.all()` or `.first()` from the end and replace with `).scalars().all()` etc.
    # But ONLY for that statement!
    
    lines = c.split("\n")
    # Actually just a while loop matching db.query(...)
    
    pass

with open("backend/temp_migrate.py", "w") as x: pass
