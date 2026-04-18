import sys
import glob

def fix_e402(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    imports = []
    other_lines = []
    
    inside_docstring = False
    doc_char = ""
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if not inside_docstring and (stripped.startswith('"""') or stripped.startswith("'''") or stripped.endswith('"""') or stripped.endswith("'''")):
            if (stripped.startswith('"""') and stripped.endswith('"""') and len(stripped) > 3) or \
               (stripped.startswith("'''") and stripped.endswith("'''") and len(stripped) > 3):
                other_lines.append(line)
                continue
               
            doc_char = '"""' if stripped.startswith('"""') else "'''"
            inside_docstring = True
            other_lines.append(line)
            continue
            
        if inside_docstring:
            other_lines.append(line)
            if doc_char in stripped:
                inside_docstring = False
            continue
            
        if line.startswith("import ") or line.startswith("from "):
            if "from __future__" in line:
                imports.insert(0, line)
            elif "from typing_extensions import Self" in line or "from typing import Self" in line:
                other_lines.append(line) # keep local imports or try/except embedded
            else:
                imports.append(line)
        else:
            other_lines.append(line)
            
    with open(filepath, "w", encoding="utf-8") as f:
        for imp in imports:
            f.write(imp)
        for line in other_lines:
            f.write(line)

for filepath in glob.glob("backend/app/**/*.py", recursive=True):
    fix_e402(filepath)

print("Fixed all E402")
