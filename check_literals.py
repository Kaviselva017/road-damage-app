import os

def check_file(path, out):
    out.write(f"\nChecking: {path}\n")
    if not os.path.exists(path):
        out.write("File does not exist.\n")
        return
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    backticks = []
    escaped = False
    for i, char in enumerate(content):
        if char == '\\' and not escaped:
            escaped = True
        elif char == '`' and not escaped:
            backticks.append(i)
            escaped = False
        else:
            escaped = False
            
    if len(backticks) % 2 != 0:
        out.write("!!! ODD NUMBER OF BACKTICKS !!!\n")
        last_idx = backticks[-1]
        line_num = content.count('\n', 0, last_idx) + 1
        out.write(f"Lone backtick at line {line_num}: {content.splitlines()[line_num-1]}\n")
    else:
        out.write("All backticks are paired.\n")
        # Check for non-escaped backticks that might be swallowed by nested literals
        # Actually, let's just look at line 780 in both files
        lines = content.splitlines()
        if len(lines) >= 780:
            out.write(f"Line 780: {lines[779]}\n")
        else:
            out.write(f"File only has {len(lines)} lines\n")

with open('d:/python/road-damage-app/literal_report.txt', 'w', encoding='utf-8') as out:
    check_file('d:/python/road-damage-app/backend/static/dashboard.html', out)
    check_file('d:/python/road-damage-app/frontend/dashboard.html', out)
