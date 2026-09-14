import os
import re

path = os.path.expanduser('~/hashverify/templates/vakalatnama.html')

with open(path, 'r') as f:
    html = f.read()

# Replace the previous basic script with the render-aware script
old_script_pattern = r'<!-- Auto-fill from Profile LocalStorage -->.*?</script>'
new_script = """<!-- Auto-fill from Profile LocalStorage -->
<script>
document.addEventListener('DOMContentLoaded', () => {
  const savedName = localStorage.getItem('advName');
  
  if (savedName) {
    const advInput = document.getElementById('advocate');
    if (advInput) {
      advInput.value = savedName;
      // Force the form's custom update function to trigger the live preview
      if (typeof update === 'function') {
        update(advInput, 'advocate', 80);
      }
    }
  }
});
</script>"""

html = re.sub(old_script_pattern, new_script, html, flags=re.DOTALL)

with open(path, 'w') as f:
    f.write(html)

print("Vakalatnama auto-fill updated to trigger live preview.")
