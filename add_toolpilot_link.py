import os

path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(path, 'r') as f:
    html = f.read()

# Clean CSS badge linking to ToolPilot
backlink_html = """
<!-- ToolPilot Directory Backlink -->
<div style="text-align: center; padding: 20px 20px 40px; clear: both;">
  <a href="https://www.toolpilot.ai" target="_blank" style="text-decoration: none; color: #64748b; font-size: 11px; font-weight: 600; display: inline-flex; align-items: center; gap: 8px; border: 1px solid #e2e8f0; padding: 6px 12px; border-radius: 8px; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
    <svg viewBox="0 0 24 24" style="width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 2;"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
    Featured on ToolPilot
  </a>
</div>
"""

# Inject right before the bottom app navigation
if "https://www.toolpilot.ai" not in html:
    html = html.replace("<!-- Mobile App Bottom Nav -->", backlink_html + "\n<!-- Mobile App Bottom Nav -->")
    with open(path, 'w') as f:
        f.write(html)
    print("ToolPilot backlink injected successfully.")
else:
    print("ToolPilot link is already on the page.")
