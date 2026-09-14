import os
import re

path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(path, 'r') as f:
    html = f.read()

# Native, highly professional inline badge matching ToolPilot brand guidelines
inline_badge_html = """<!-- ToolPilot Directory Backlink -->
<div style="text-align: center; padding: 30px 20px 60px; clear: both;">
  <a href="https://www.toolpilot.ai" target="_blank" style="display: inline-flex; align-items: center; gap: 10px; background: #0f172a; color: #fff; padding: 10px 18px; border-radius: 12px; text-decoration: none; border: 1px solid #334155; box-shadow: 0 4px 12px rgba(0,0,0,0.1); transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.03)'" onmouseout="this.style.transform='scale(1)'">
    <div style="font-weight: 800; font-size: 16px; letter-spacing: -0.05em; background: #3b82f6; color: #fff; padding: 4px 8px; border-radius: 6px; font-family: monospace;">TP</div>
    <div style="text-align: left; line-height: 1.2;">
      <div style="font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em; color: #94a3b8; font-weight: 600;">Featured on</div>
      <div style="font-size: 13px; font-weight: 700; letter-spacing: 0.05em; font-family: sans-serif;">TOOL PILOT</div>
    </div>
  </a>
</div>"""

# Replace any existing ToolPilot backlink block
old_pattern = r'<!-- ToolPilot Directory Backlink -->.*?</div>\s*</div>'

if re.search(old_pattern, html, flags=re.DOTALL):
    html = re.sub(old_pattern, inline_badge_html, html, flags=re.DOTALL)
else:
    # Fallback replacement targeting the img tag block
    html = re.sub(r'<!-- ToolPilot Directory Backlink -->.*?</div>', inline_badge_html, html, flags=re.DOTALL)

with open(path, 'w') as f:
    f.write(html)

print("ToolPilot badge updated to robust inline vector design.")
