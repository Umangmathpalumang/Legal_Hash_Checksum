import os

path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(path, 'r') as f:
    html = f.read()

mobile_css = """
/* APP-LIKE MOBILE VIEW */
@media (max-width: 768px) {
  body { background: #f4f7fb; }
  nav { display: none; } /* Hide standard top nav */
  
  /* Dark Header matching mockup */
  .hero {
    background: #0f172a; 
    color: #fff;
    padding: 50px 20px 30px;
    border-bottom-left-radius: 24px;
    border-bottom-right-radius: 24px;
    text-align: center;
  }
  .hero h1 { font-size: 24px; color: #fff; margin-bottom: 4px; }
  .hero h1 em { color: #fff; font-style: normal; }
  .hero-desc { font-size: 13px; color: #cbd5e1; margin-bottom: 0; }
  .hero-eyebrow, .stat-strip, .cat-bar-wrap { display: none; }
  
  /* Mock Search Bar */
  .hero::after {
    content: "🔍 Search tools...";
    display: block;
    background: #f8fafc;
    color: #64748b;
    padding: 12px 18px;
    border-radius: 24px;
    font-size: 14px;
    text-align: left;
    margin-top: 24px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  }

  /* 3-Column Grid for Tools */
  .tools-wrap { padding: 24px 16px 110px; }
  .tools-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  
  /* App Icon Cards */
  .tool-card {
    background: #fff;
    border: none;
    border-radius: 18px;
    padding: 16px 8px;
    align-items: center;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
  }
  .card-head { margin: 0 0 10px 0; justify-content: center; width: 100%; }
  .card-meta, .card-desc, .card-foot { display: none; }
  .card-icon { width: 44px; height: 44px; background: transparent !important; }
  .card-icon svg { width: 34px; height: 34px; stroke: #334155; stroke-width: 1.5; }
  .card-title { font-size: 11px; font-weight: 600; color: #1e293b; line-height: 1.2; }

  /* Bottom App Navigation */
  .app-nav {
    display: flex;
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: #fff;
    padding: 12px 24px calc(12px + env(safe-area-inset-bottom));
    justify-content: space-between;
    border-top: 1px solid #e2e8f0;
    z-index: 1000;
  }
  .app-nav-item {
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    text-decoration: none; color: #94a3b8; font-size: 10px; font-weight: 600;
  }
  .app-nav-item.active { color: #0f172a; }
  .app-nav-item svg { width: 24px; height: 24px; stroke: currentColor; fill: none; stroke-width: 1.8; }
  .app-nav-item.active svg { fill: #0f172a; stroke: none; }
  
  footer { display: none; }
  .fb-btn { bottom: 85px; right: 16px; transform: scale(0.85); }
}
@media (min-width: 769px) { .app-nav { display: none; } }
</style>
"""

bottom_nav_html = """
<!-- Mobile App Bottom Nav -->
<div class="app-nav">
  <a href="/" class="app-nav-item">
    <svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
    Home
  </a>
  <a href="#" class="app-nav-item">
    <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
    Cases
  </a>
  <a href="/tools" class="app-nav-item active">
    <svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
    Tools
  </a>
  <a href="#" class="app-nav-item">
    <svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
    Alerts
  </a>
  <a href="#" class="app-nav-item">
    <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
    Profile
  </a>
</div>
</body>
"""

if "APP-LIKE MOBILE VIEW" not in html:
    html = html.replace("</style>", mobile_css)
    html = html.replace("</body>", bottom_nav_html)
    
    with open(path, 'w') as f:
        f.write(html)
    print("Mobile app view injected successfully.")
else:
    print("Mobile view already applied.")
