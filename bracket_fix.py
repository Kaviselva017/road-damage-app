import os
import glob
import re

files = glob.glob("backend/app/**/*.py", recursive=True)

def find_matching_bracket(s, start):
    count = 0
    for i in range(start, len(s)):
        if s[i] == '(': count += 1
        elif s[i] == ')': count -= 1
        if count == 0: return i
    return -1

for path in files:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    orig = content
    while "db.query(" in content:
        idx = content.find("db.query(")
        # We want to replace db.query(Model) with db.execute(select(Model)).scalars() 
        # BUT only after the whole query chain.
        # It's much easier to:
        # 1. find db.query
        # 2. Extract model string
        # 3. Find the end of `.all()` or `.first()` or `.count()`
        break

    # Alternative:
    # A generic script that uses regex matching up to `.all()` or `.first()` or `.scalar()`
    # but strictly matching valid python idents and whitespace/newlines.
    
    # Wait! In SQLAlchemy 2.0, you just do db.scalars(select(Model).filter(...)).all()
    # So we need to wrap the whole expression from `db.query` to just before `.all()` in `db.scalars`? No, select(...) is what we need.
    pass
