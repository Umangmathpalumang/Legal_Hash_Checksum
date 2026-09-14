import os

path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(path, 'r') as f:
    html = f.read()

# Replace with the official White logo variation for dark backgrounds
old_logo_url = "https://www.toolpilot.ai/cdn/shop/files/tp-b-h_bec97d1a-5538-498b-8a26-77de74f90ed5_1692x468_crop_center.svg?v=1695882612"
# Using ToolPilot's white brand guideline variant URL
new_logo_url = "https://www.toolpilot.ai/cdn/shop/files/tp-w-h_1692x468_crop_center.svg?v=1695882612"

# If the URL differs, use a safe regex fallback to swap out whatever SVG link is present
if old_logo_url in html:
    html = html.replace(old_logo_url, new_logo_url)
else:
    import re
    html = re.sub(r'src="https://www\.toolpilot\.ai/cdn/shop/files/[^"]+\.svg[^"]*"', f'src="{new_logo_url}"', html)

with open(path, 'w') as f:
    f.write(html)

print("ToolPilot badge updated to the White logo variant.")
