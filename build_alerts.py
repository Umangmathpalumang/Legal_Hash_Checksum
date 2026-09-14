import os
import re

alerts_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Alerts</title>
  <style>
    body { background: #f4f7fb; font-family: 'Inter', sans-serif; margin: 0; padding-bottom: 80px; }
    .header { background: #0f172a; color: #fff; padding: 50px 20px 30px; border-radius: 0 0 24px 24px; text-align: center; }
    .header h1 { margin: 0; font-size: 24px; letter-spacing: -0.02em; }
    .header p { color: #cbd5e1; font-size: 13px; margin: 6px 0 0; font-weight: 400; }
    .container { padding: 24px 16px; max-width: 480px; margin: 0 auto; }
    
    .alert-card { background: #fff; padding: 16px; border-radius: 16px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); border-left: 4px solid #3b82f6; display: flex; gap: 12px; align-items: flex-start; }
    .alert-card.urgent { border-left-color: #ef4444; }
    .alert-icon { width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; background: #eff6ff; color: #3b82f6; }
    .alert-card.urgent .alert-icon { background: #fef2f2; color: #ef4444; }
    .alert-icon svg { width: 18px; height: 18px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .alert-content { flex: 1; }
    .alert-title { font-size: 14px; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
    .alert-desc { font-size: 12px; color: #64748b; line-height: 1.4; }
    .alert-time { font-size: 11px; color: #94a3b8; margin-top: 6px; font-weight: 600; display: flex; align-items: center; gap: 4px; }
    .empty-state { text-align: center; padding: 40px 20px; color: #64748b; font-size: 14px; }

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
    <h1>Notifications</h1>
    <p>Upcoming hearings & reminders</p>
  </div>
  
  <div class="container" id="alertsList"></div>

  <div class="app-nav">
    <a href="/" class="app-nav-item"><svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>Home</a>
    <a href="/cases" class="app-nav-item"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>Cases</a>
    <a href="/tools" class="app-nav-item"><svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>Tools</a>
    <a href="/alerts" class="app-nav-item active"><svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>Alerts</a>
    <a href="/profile" class="app-nav-item"><svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>Profile</a>
  </div>

  <script>
    function generateAlerts() {
      const cases = JSON.parse(localStorage.getItem('lhc_user_cases') || '[]');
      const alertsList = document.getElementById('alertsList');
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      
      let generatedAlerts = [];

      cases.forEach(c => {
        if (!c.date || c.date === 'TBD') return;
        const hearingDate = new Date(c.date);
        if (isNaN(hearingDate)) return;
        
        const diffTime = hearingDate - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        if (diffDays >= 0 && diffDays <= 7) {
          generatedAlerts.push({
            id: c.id,
            client: c.client,
            court: c.court,
            days: diffDays,
            dateStr: hearingDate.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
          });
        }
      });

      generatedAlerts.sort((a, b) => a.days - b.days);

      if (generatedAlerts.length === 0) {
        alertsList.innerHTML = '<div class="empty-state">No upcoming hearings in the next 7 days.<br><br>Cases added with dates will appear here automatically.</div>';
        return;
      }

      generatedAlerts.forEach(a => {
        const isUrgent = a.days <= 1;
        const urgencyText = a.days === 0 ? "Today" : a.days === 1 ? "Tomorrow" : `In ${a.days} days`;
        
        alertsList.innerHTML += `
          <div class="alert-card ${isUrgent ? 'urgent' : ''}">
            <div class="alert-icon">
              <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            </div>
            <div class="alert-content">
              <div class="alert-title">Hearing ${urgencyText}</div>
              <div class="alert-desc"><strong>${a.id}</strong><br>${a.client}<br>${a.court}</div>
              <div class="alert-time">🗓 ${a.dateStr}</div>
            </div>
          </div>
        `;
      });
    }

    generateAlerts();
  </script>
</body>
</html>"""

with open(os.path.expanduser('~/hashverify/templates/alerts.html'), 'w') as f:
    f.write(alerts_html)

# 2. Add Route to main.py
main_path = os.path.expanduser('~/hashverify/main.py')
with open(main_path, 'r') as f:
    main_code = f.read()

alerts_route = """
@app.get("/alerts", response_class=HTMLResponse)
async def get_alerts():
    with open("templates/alerts.html", "r", encoding="utf-8") as f:
        return f.read()
"""
if '@app.get("/alerts"' not in main_code:
    with open(main_path, 'a') as f:
        f.write(alerts_route)

# 3. Wire the Alerts navigation icon across existing HTML templates
for template in ['tools.html', 'cases.html']:
    filepath = os.path.expanduser(f'~/hashverify/templates/{template}')
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            html = f.read()
        
        # Replace the javascript void link with the real route
        old_alert_link = r'<a href="javascript:void\(0\)" onclick="alert\(\'Module in development\'\)" class="app-nav-item">\s*<svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>\s*Alerts\s*</a>'
        new_alert_link = """<a href="/alerts" class="app-nav-item">
    <svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
    Alerts
  </a>"""
        
        html = re.sub(old_alert_link, new_alert_link, html)
        with open(filepath, 'w') as f:
            f.write(html)

print("Alerts module active and linked.")
