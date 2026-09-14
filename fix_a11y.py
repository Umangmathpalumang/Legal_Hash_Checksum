import os

path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(path, 'r') as f:
    html = f.read()

# 1. Accessible Name for screen readers
html = html.replace(
    '<button class="fb-x" onclick="fbClose()">',
    '<button class="fb-x" aria-label="Close feedback" onclick="fbClose()">'
)

# 2. Document Main Landmark
if '<main>' not in html:
    html = html.replace('</nav>', '</nav>\n<main>')
    html = html.replace('<footer>', '</main>\n<footer>')

# 3. Color Contrast Ratio (Darkening text for AA compliance)
html = html.replace('color:var(--green);border:1px', 'color:#15803d;border:1px')
html = html.replace('color:var(--accent-light);font-size:11px', 'color:var(--accent);font-size:11px')
html = html.replace('color:var(--accent-light)}', 'color:var(--accent)}')

with open(path, 'w') as f:
    f.write(html)

print("Accessibility patches applied successfully.")
