import os

path = os.path.expanduser('~/hashverify/templates/tools.html')
with open(path, 'r') as f:
    html = f.read()

# 1. Swap mock search CSS for real input CSS
old_css = """  /* Mock Search Bar */
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
  }"""

new_css = """  /* Real Search Bar */
  .mobile-search-box {
    width: 100%;
    background: #f8fafc;
    color: #1e293b;
    padding: 12px 18px;
    border-radius: 24px;
    border: none;
    font-size: 14px;
    margin-top: 24px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    outline: none;
  }
  .mobile-search-box::placeholder { color: #64748b; }"""
html = html.replace(old_css, new_css)

# 2. Inject the HTML input field
if 'id="mobileSearch"' not in html:
    html = html.replace('<div class="stat-strip">', 
                        '<input type="text" id="mobileSearch" class="mobile-search-box" placeholder="🔍 Search tools..." onkeyup="filterTools()">\n  <div class="stat-strip">')

# 3. Add the JavaScript filtering logic
if 'function filterTools()' not in html:
    js = """
function filterTools() {
  var input = document.getElementById('mobileSearch').value.toLowerCase();
  document.querySelectorAll('.tool-card').forEach(function(card) {
    var title = card.querySelector('.card-title').innerText.toLowerCase();
    card.style.display = title.includes(input) ? '' : 'none';
  });
}
</script>"""
    html = html.replace('</script>', js)

# 4. Wire the inactive nav icons to a prototype alert
html = html.replace('href="#"', 'href="javascript:void(0)" onclick="alert(\'Module in development\')"')

with open(path, 'w') as f:
    f.write(html)

print("Search engine and nav links injected.")
