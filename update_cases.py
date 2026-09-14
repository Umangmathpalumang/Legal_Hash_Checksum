import os

cases_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cases Docket</title>
  <style>
    body { background: #f4f7fb; font-family: 'Inter', sans-serif; margin: 0; padding-bottom: 80px; }
    .header { background: #0f172a; color: #fff; padding: 50px 20px 30px; text-align: center; border-radius: 0 0 24px 24px; }
    .header h1 { margin: 0; font-size: 24px; letter-spacing: -0.02em; }
    .header p { color: #cbd5e1; font-size: 13px; margin: 6px 0 0; font-weight: 400; }
    .container { padding: 24px 16px; max-width: 480px; margin: 0 auto; }
    .case-card { background: #fff; padding: 18px; border-radius: 16px; margin-bottom: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); border: 1px solid #f1f5f9; }
    .case-id { font-size: 11px; color: #64748b; font-weight: 700; letter-spacing: 0.05em; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
    .case-status { color: #10b981; background: #d1fae5; padding: 3px 10px; border-radius: 20px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; border: 1px solid rgba(16,185,129,0.2); }
    .case-client { font-size: 15px; font-weight: 700; color: #1e293b; margin-bottom: 6px; line-height: 1.3; }
    .case-type { font-size: 13px; color: #475569; margin-bottom: 16px; display: flex; align-items: center; gap: 6px; }
    .case-type svg { width: 14px; height: 14px; stroke: #94a3b8; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .case-meta { display: flex; flex-direction: column; gap: 8px; font-size: 12px; font-weight: 500; padding-top: 14px; border-top: 1px solid #f1f5f9; }
    .meta-row { display: flex; justify-content: space-between; align-items: center; }
    .meta-item { display: flex; align-items: center; gap: 6px; color: #64748b; }
    .meta-item svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .court-name { color: #334155; }
    .hearing-date { color: #d97706; font-weight: 600; background: #fef3c7; padding: 4px 8px; border-radius: 6px; }
    
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
    <p>Encrypted local docket management</p>
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
    // Realistic Indian Court Data
    const mockCases = [
      { 
        id: "Bail Appln. 1452/2026", 
        client: "State of NCT of Delhi vs. Vikram Singh", 
        type: "BNS 103, 109 (Murder, Attempt to Murder)", 
        court: "Patiala House Courts, New Delhi", 
        date: "Sep 14, 2026", 
        status: "Arguments" 
      },
      { 
        id: "CS(COMM) 201/2026", 
        client: "Reliance Retail Ltd vs. Sharma Distributors", 
        type: "Commercial Suit (IPR Infringement)", 
        court: "Delhi High Court", 
        date: "Sep 18, 2026", 
        status: "Order Reserved" 
      },
      { 
        id: "CC No. 4509/2025", 
        client: "HDFC Bank Ltd vs. Manish Kumar", 
        type: "Sec 138 NI Act (Cheque Bounce)", 
        court: "Tis Hazari Courts, Delhi", 
        date: "Sep 22, 2026", 
        status: "Cross Exam" 
      },
      { 
        id: "HMA No. 892/2025", 
        client: "Sneha Desai vs. Rohan Desai", 
        type: "Sec 13(1) Hindu Marriage Act", 
        court: "Family Court, Dwarka", 
        date: "Oct 05, 2026", 
        status: "Evidence" 
      }
    ];

    const docketList = document.getElementById('docketList');
    mockCases.forEach(c => {
      docketList.innerHTML += `
        <div class="case-card">
          <div class="case-id">
            <span>${c.id}</span> 
            <span class="case-status">${c.status}</span>
          </div>
          <div class="case-client">${c.client}</div>
          <div class="case-type">
            <svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            ${c.type}
          </div>
          <div class="case-meta">
            <div class="meta-row">
              <span class="meta-item court-name">
                <svg viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                ${c.court}
              </span>
            </div>
            <div class="meta-row" style="justify-content: flex-end;">
              <span class="meta-item hearing-date">
                <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                ${c.date}
              </span>
            </div>
          </div>
        </div>
      `;
    });
  </script>
</body>
</html>"""

with open(os.path.expanduser('~/hashverify/templates/cases.html'), 'w') as f:
    f.write(cases_html)

print("Cases prototype upgraded with professional SVGs and realistic data.")
