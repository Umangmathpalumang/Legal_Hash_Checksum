with open('index.html', 'r') as f:
    html = f.read()

# 1. Clean up the misplaced links from the middle of the page
bad_injection = '''<span style="color:var(--tx3)">legalhashchecksum.com</span>
    <div style="margin-top: 15px; display: flex; justify-content: center; gap: 20px; align-items: center;">
      <a href="/tools" style="color:var(--ac); text-decoration:none; font-size:13px; font-weight:600;">Browse All Legal Tools</a>
      <a href="https://www.toolpilot.ai/" target="_blank" rel="noopener noreferrer" style="color:var(--tx2); text-decoration:none; font-size:13px; font-weight:500;">Featured on Toolpilot.ai</a>
    </div>'''

html = html.replace(bad_injection, '<span style="color:var(--tx3)">legalhashchecksum.com</span>')

# 2. Inject the links at the absolute bottom of the SEO section
true_bottom = '''
  <div style="text-align: center; padding-top: 40px; margin-top: 40px; border-top: 1px solid var(--bd);">
    <div style="display: flex; justify-content: center; gap: 20px; align-items: center;">
      <a href="/tools" style="color:var(--ac); text-decoration:none; font-size:14px; font-weight:600;">Browse All Legal Tools</a>
      <span style="color:var(--tx3)">|</span>
      <a href="https://www.toolpilot.ai/" target="_blank" rel="noopener noreferrer" style="color:var(--tx2); text-decoration:none; font-size:14px; font-weight:500;">Featured on Toolpilot.ai</a>
    </div>
  </div>
</section>'''

# Ensure we don't double-inject if run multiple times
if "Browse All Legal Tools" not in html.split("</section>")[-2]:
    html = html.replace('</section>', true_bottom)

with open('index.html', 'w') as f:
    f.write(html)
    
print("✅ Links moved to the absolute bottom of the page.")
