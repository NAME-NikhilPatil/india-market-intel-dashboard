"""Combine template + data + renderers into a single self-contained HTML."""
import json, os, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
template = open(os.path.join(BASE, 'dashboard_template.html')).read()
renderers = open(os.path.join(BASE, 'dashboard_renderers.js')).read()
data = open(os.path.join(BASE, 'dashboard_data.json')).read()

# Inject (use replace; placeholders are unique strings, not regex)
out = template.replace('__DATA__', data).replace('__CHART_RENDERERS__', renderers)

target = os.path.join(BASE, 'solar_dcr_dashboard.html')
with open(target, 'w') as f:
    f.write(out)
size = os.path.getsize(target)
print(f"Wrote {target} ({size:,} bytes / {size/1024/1024:.2f} MB)")
