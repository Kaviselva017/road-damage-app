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
        
        # Docstring toggles
        if not inside_docstring and (stripped.startswith('"""') or stripped.startswith("'''") or stripped.endswith('"""') or stripped.endswith("'''")):
            # handle single line docstrings
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
            
        # If it's an import at column 0
        if line.startswith("import ") or line.startswith("from "):
            if "from __future__" in line:
                imports.insert(0, line)
            else:
                imports.append(line)
        else:
            other_lines.append(line)
            
    # Write back
    new_content = ""
    for imp in imports:
        new_content += imp
    for line in other_lines:
        new_content += line
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

for bad in ["backend/app/main.py", "backend/app/services/ai_service.py", "backend/app/services/auth_service.py"]:
    fix_e402(bad)

print("Fixed E402")
