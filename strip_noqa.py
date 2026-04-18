import os
import glob
import re

for file_path in glob.glob('backend/app/**/*.py', recursive=True):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    # Remove # ruff: noqa: ...
    content = re.sub(r'(?m)^# ruff: noqa:.*$', '', content)
    # Remove inline # noqa: ...
    content = re.sub(r'  # noqa:.*$', '', content, flags=re.MULTILINE)
    # Remove single # noqa...
    content = re.sub(r'# noqa:.*$', '', content, flags=re.MULTILINE)

    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
