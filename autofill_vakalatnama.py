import os

path = os.path.expanduser('~/hashverify/templates/vakalatnama.html')

if os.path.exists(path):
    with open(path, 'r') as f:
        html = f.read()

    js_injection = """
<!-- Auto-fill from Profile LocalStorage -->
<script>
document.addEventListener('DOMContentLoaded', () => {
  const savedName = localStorage.getItem('advName');
  const savedBar = localStorage.getItem('advBar');
  const savedPhone = localStorage.getItem('advPhone');
  
  // Fuzzy targeting for your form fields (matches IDs or placeholders)
  const nameInputs = document.querySelectorAll('input[id*="name" i], input[placeholder*="Advocate Name" i]');
  const barInputs = document.querySelectorAll('input[id*="bar" i], input[placeholder*="Enrollment" i], input[placeholder*="Bar Council" i]');
  const phoneInputs = document.querySelectorAll('input[id*="phone" i], input[id*="mobile" i], input[placeholder*="Phone" i]');

  if (savedName && nameInputs.length > 0) nameInputs.forEach(i => i.value = savedName);
  if (savedBar && barInputs.length > 0) barInputs.forEach(i => i.value = savedBar);
  if (savedPhone && phoneInputs.length > 0) phoneInputs.forEach(i => i.value = savedPhone);
});
</script>
</body>"""

    if "Auto-fill from Profile LocalStorage" not in html:
        html = html.replace('</body>', js_injection)
        with open(path, 'w') as f:
            f.write(html)
        print("Vakalatnama auto-fill injected successfully.")
    else:
        print("Auto-fill already present.")
else:
    print("vakalatnama.html not found. Check the filename.")
