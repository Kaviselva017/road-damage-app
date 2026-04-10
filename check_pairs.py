import os

def check_file(path):
    print(f"\nChecking: {path}")
    if not os.path.exists(path):
        print("File does not exist.")
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
            
    print(f"Total uncovered backticks: {len(backticks)}")
    
    if len(backticks) % 2 != 0:
        print("!!! ODD NUMBER OF BACKTICKS (Unterminated template literal found) !!!")
        last_idx = backticks[-1]
        line = content.count('\n', 0, last_idx) + 1
        print(f"Lone backtick is at line {line}, index {last_idx}")
        start = max(0, last_idx - 50)
        end = min(len(content), last_idx + 50)
        print(f"Context: ...{content[start:end]}...")
    else:
        print("All backticks are paired.")
        # Now check for unbalanced ${ } within pairs
        for i in range(0, len(backticks), 2):
            start_btn = backticks[i]
            end_btn = backticks[i+1]
            snippet = content[start_btn:end_btn+1]
            open_braces = snippet.count('${')
            close_braces = snippet.count('}')
            if open_braces != close_braces:
                line = content.count('\n', 0, start_btn) + 1
                print(f"Unbalanced braces in template literal starting at line {line}")
                print(f"Snippet: {snippet[:100]}...")

check_file('d:/python/road-damage-app/backend/static/dashboard.html')
check_file('d:/python/road-damage-app/frontend/dashboard.html')
