with open('tools.html', 'r') as f:
    html = f.read()

# The clean vector SVG badge matching the Toolpilot brand
svg_badge = '''
    <div style="margin-top: 25px; display: flex; justify-content: center; width: 100%;">
      <a href="https://www.toolpilot.ai/" target="_blank" rel="noopener noreferrer" style="display:inline-block; transition:transform 0.2s ease;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'" aria-label="Featured on Toolpilot">
        <svg width="145" height="32" viewBox="0 0 160 36" fill="none" xmlns="http://www.w3.org/2000/svg">
          <!-- T -->
          <path d="M4 8H18V11.5H13V28H9V11.5H4V8Z" fill="#7C3AED"/>
          <!-- P -->
          <path d="M19 8H29C32.866 8 36 11.134 36 15C36 18.866 32.866 22 29 22H23V28H19V8ZM23 11.5V18.5H29C30.933 18.5 32.5 16.933 32.5 15C32.5 13.067 30.933 11.5 29 11.5H23Z" fill="#7C3AED"/>
          <!-- Text -->
          <text x="42" y="23" font-family="'Inter', system-ui, sans-serif" font-weight="800" font-size="16" fill="#64748B" letter-spacing="1.5">TOOLPILOT</text>
        </svg>
      </a>
    </div>'''

# Inject directly beneath the legalhashchecksum.com footer text
if "legalhashchecksum.com</a>" in html:
    html = html.replace("legalhashchecksum.com</a>", "legalhashchecksum.com</a>" + svg_badge)
elif "legalhashchecksum.com</span>" in html:
    html = html.replace("legalhashchecksum.com</span>", "legalhashchecksum.com</span>" + svg_badge)
elif "legalhashchecksum.com" in html:
    html = html.replace("legalhashchecksum.com", "legalhashchecksum.com" + svg_badge)

with open('tools.html', 'w') as f:
    f.write(html)
    
print("✅ Toolpilot SVG badge successfully injected into tools.html footer.")
