import os
import re

path = os.path.expanduser('~/hashverify/main.py')
with open(path, 'r') as f:
    code = f.read()

# Target the exact broken block
pattern = r'@app\.get\("/profile", response_class=HTMLResponse\)\s*async def get_profile\(request: Request\):\s*return templates\.TemplateResponse\("profile\.html", \{"request": request\}\)'

# Replace it with a direct HTML string return (bypassing Jinja2 dependencies)
safe_route = """@app.get("/profile", response_class=HTMLResponse)
async def get_profile():
    with open("templates/profile.html", "r", encoding="utf-8") as f:
        return f.read()"""

fixed_code = re.sub(pattern, safe_route, code)

with open(path, 'w') as f:
    f.write(fixed_code)

print("Profile route patched successfully!")
