import os
import re

# 1. Create cases.html
cases_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cases Docket</title>
  <style>
    body { background: #f4f7fb; font-family: 'Inter', sans-serif; margin: 0; padding-bottom: 80px; }
    .header { background: #0f172a; color: #fff; padding: 50px 20px 30px; text-align: center; border-radius: 0 0 24px 24px; }
    .header h1 { margin: 0; font-size: 24px; }
    .header p { color: #cbd5e1; font-size: 13px; margin: 6px 0 0; }
    .container { padding: 24px 16px; max-width: 480px; margin: 0 auto; }
    .case-card { background: #fff; padding: 18px; border-radius: 16px; margin-bottom: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }
    .case-id { font-size: 11px; color: #64748b; font-weight: 700; letter-spacing: 0.05em; margin-bottom: 6px; display: flex; justify-content: space-between; }
    .case-status { color: #10b981; background: #d1fae5; padding: 2px 8px; border-radius: 12px; }
    .case-client { font-size: 16px; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
    .case-type { font-size: 13px; color: #475569; margin-bottom: 14px; }
    .case-meta { display: flex; justify-content: space-between; font-size: 12px; font-weight: 600; padding-top: 14px; border-top: 1px dashed #e2e8f0; }
    .hearing-date { color: #d97706; display: flex; align-items: center; gap: 4px; }
    .court-name { color: #2563eb; }
    
    /* Bottom Nav */
    .app-nav { display: flex; position: fixed; bottom: 0; left: 0; right: 0; background: #fff; padding: 12px 24px calc(12px + env(safe-area-inset-bottom)); justify-content: space-between; border-top: 1px solid #e2e8f0; z-index: 1000; }
    .app-nav-item { display: flex; flex-direction: column; align-items: center; gap: 4px; text-decoration: none; color: #94a3b8; font-size: 10px; font-weight: 600; }
    .app-nav-item.active { color: #0f172a; }
    .app-nav-item svg { width: 24px; height: 24px; stroke: currentColor; fill: none; stroke-width: 1.8; }
    .app-nav-item.active svg { fill: #0f172a; stroke: none; }
  </style>
</head>
<body>
  <div class="header">
    <h1>Active Cases</h1>
    <p>Local zero-trust docket prototype</p>
  </div>
  
  <div class="container" id="docketList"></div>

  <div class="app-nav">
    <a href="/" class="app-nav-item"><svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>Home</a>
    <a href="/cases" class="app-nav-item active"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>Cases</a>
    <a href="/tools" class="app-nav-item"><svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>Tools</a>
    <a href="javascript:void(0)" onclick="alert('Module in development')" class="app-nav-item"><svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>Alerts</a>
    <a href="/profile" class="app-nav-item"><svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>Profile</a>
  </div>

  <script>
    // Static JSON array of dummy clients
    const mockCases = [
      { id: "CR-2026-88", client: "Rajesh Sharma", type: "Bail Application (Sec 439)", court: "Sessions Court, Delhi", date: "Sep 12, 2026", status: "Hearing" },
      { id: "CV-2025-14", client: "Priya Patel vs. Amit Patel", type: "Divorce Petition", court: "Family Court, Dwarka", date: "Sep 15, 2026", status: "Evidence" },
      { id: "NI-138-09", client: "TechCorp India Pvt Ltd", type: "Cheque Bounce (Sec 138)", court: "Saket District Court", date: "Sep 21, 2026", status: "Cross Exam" }
    ];

    const docketList = document.getElementById('docketList');
    mockCases.forEach(c => {
      docketList.innerHTML += `
        <div class="case-card">
          <div class="case-id"><span>${c.id}</span> <span class="case-status">${c.status}</span></div>
          <div class="case-client">${c.client}</div>
          <div class="case-type">${c.type}</div>
          <div class="case-meta">
            <span class="court-name">📍 ${c.court}</span>
            <span class="hearing-date">🗓 ${c.date}</span>
          </div>
        </div>
      `;
    });
  </script>
</body>
</html>"""
with open(os.path.expanduser('~/hashverify/templates/cases.html'), 'w') as f:
    f.write(cases_html)

# 2. Add Route to main.py
main_path = os.path.expanduser('~/hashverify/main.py')
with open(main_path, 'r') as f:
    main_code = f.read()

cases_route = """
@app.get("/cases", response_class=HTMLResponse)
async def get_cases():
    with open("templates/cases.html", "r", encoding="utf-8") as f:
        return f.read()
"""
if '@app.get("/cases"' not in main_code:
    with open(main_path, 'a') as f:
        f.write(cases_route)

# 3. Wire the Cases navigation icon in tools.html
tools_path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(tools_path, 'r') as f:
    tools_html = f.read()

old_link = r'<a href="javascript:void\(0\)" onclick="alert\(\'Module in development\'\)" class="app-nav-item">\s*<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>\s*Cases\s*</a>'
new_link = """<a href="/cases" class="app-nav-item">
    <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
    Cases
  </a>"""

tools_html = re.sub(old_link, new_link, tools_html)
with open(tools_path, 'w') as f:
    f.write(tools_html)

print("Cases prototype built, routed, and linked successfully.")
