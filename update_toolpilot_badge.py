import os
import re

path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(path, 'r') as f:
    html = f.read()

# Official SVG badge block
new_badge_html = """<!-- ToolPilot Directory Backlink -->
<div style="text-align: center; padding: 30px 20px 60px; clear: both;">
  <a href="https://www.toolpilot.ai" target="_blank" style="display: inline-block; transition: opacity 0.2s;" onmouseover="this.style.opacity=0.8" onmouseout="this.style.opacity=1">
    <img src="https://www.toolpilot.ai/cdn/shop/files/tp-b-h_bec97d1a-5538-498b-8a26-77de74f90ed5_1692x468_crop_center.svg?v=1695882612" alt="Featured on ToolPilot" style="height: 36px; width: auto; object-fit: contain;">
  </a>
</div>"""

# Target and replace the old text-based block
old_pattern = r'<!-- ToolPilot Directory Backlink -->.*?</div>'

if re.search(old_pattern, html, flags=re.DOTALL):
    html = re.sub(old_pattern, new_badge_html, html, flags=re.DOTALL)
    with open(path, 'w') as f:
        f.write(html)
    print("ToolPilot text link successfully replaced with official SVG.")
else:
    print("Could not find the original block to replace.")

