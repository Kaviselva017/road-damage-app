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
            
    out.write(f"Total uncovered backticks: {len(backticks)}\n")
    
    if len(backticks) % 2 != 0:
        out.write("!!! ODD NUMBER OF BACKTICKS !!!\n")
        last_idx = backticks[-1]
        line = content.count('\n', 0, last_idx) + 1
        out.write(f"Lone backtick at line {line}\n")
    else:
        out.write("All backticks are paired.\n")
        for i in range(0, len(backticks), 2):
            s = backticks[i]
            e = backticks[i+1]
            snippet = content[s:e+1]
            if snippet.count('${') != snippet.count('}'):
                line = content.count('\n', 0, s) + 1
                out.write(f"Unbalanced braces in template starting at line {line}\n")

with open('d:/python/road-damage-app/final_check.txt', 'w', encoding='utf-8') as out:
    check_file('d:/python/road-damage-app/backend/static/dashboard.html', out)
    check_file('d:/python/road-damage-app/frontend/dashboard.html', out)
