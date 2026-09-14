import os
import re

path = os.path.expanduser('~/hashverify/templates/alerts.html')
with open(path, 'r') as f:
    html = f.read()

old_logic = """        const hearingDate = new Date(c.date);
        if (isNaN(hearingDate)) return;
        
        const diffTime = hearingDate - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));"""

new_logic = """        // Force strict local time to prevent IST/UTC timezone drifting
        let hearingDate;
        if (c.date.includes('-')) {
          const [y, m, d] = c.date.split('-');
          hearingDate = new Date(y, m - 1, d);
        } else {
          hearingDate = new Date(c.date);
        }
        if (isNaN(hearingDate)) return;
        
        hearingDate.setHours(0, 0, 0, 0);
        
        const diffTime = hearingDate - today;
        const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));"""

if "Force strict local time" not in html:
    html = html.replace(old_logic, new_logic)
    with open(path, 'w') as f:
        f.write(html)
    print("Timezone bug patched successfully.")
else:
    print("Patch already applied.")
