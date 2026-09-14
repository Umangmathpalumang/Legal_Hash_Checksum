import os
import re

path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(path, 'r') as f:
    html = f.read()

correct_nav = """<!-- Mobile App Bottom Nav -->
<div class="app-nav">
  <a href="/" class="app-nav-item">
    <svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
    Home
  </a>
  <a href="javascript:void(0)" onclick="alert('Module in development')" class="app-nav-item">
    <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
    Cases
  </a>
  <a href="/tools" class="app-nav-item active">
    <svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
    Tools
  </a>
  <a href="javascript:void(0)" onclick="alert('Module in development')" class="app-nav-item">
    <svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
    Alerts
  </a>
  <a href="/profile" class="app-nav-item">
    <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
    Profile
  </a>
</div>
</body>"""

# Replace everything from the comment to the closing body tag
html = re.sub(r'<!-- Mobile App Bottom Nav -->.*?</body>', correct_nav, html, flags=re.DOTALL)

with open(path, 'w') as f:
    f.write(html)

print("Navigation block successfully overwritten.")
