import os
import re

path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(path, 'r') as f:
    html = f.read()

# Use regex to find the Profile icon and swap the href, ignoring whitespace formatting
pattern = r'<a href="javascript:void\(0\)" onclick="alert\([^)]+\)" class="app-nav-item">(\s*<svg.*?</svg>\s*Profile\s*)</a>'
replacement = r'<a href="/profile" class="app-nav-item">\1</a>'

new_html = re.sub(pattern, replacement, html, flags=re.DOTALL)

with open(path, 'w') as f:
    f.write(new_html)

print("Profile link successfully wired!")
