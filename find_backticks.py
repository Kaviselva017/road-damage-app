with open('d:/python/road-damage-app/frontend/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

total = content.count('`')
print(f"Total backticks: {total}")

lines = content.split('\n')
for i, line in enumerate(lines):
    if line.count('`') % 2 != 0:
        print(f"Line {i+1}: {line.strip()}")
