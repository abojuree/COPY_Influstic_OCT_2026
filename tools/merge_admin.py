import re
import os

with open("apps/templates/accounts/admin_db.html", "r", encoding="utf-8") as f:
    db_content = f.read()

with open("apps/templates/accounts/admin.html", "r", encoding="utf-8") as f:
    scan_content = f.read()

# Extract db stats and tools (from <div class="row mb-3"> to </script>)
match_db = re.search(r'<div class="row mb-3">.*?<!-- Add JavaScript for progress indicators -->.*?</script>', db_content, re.DOTALL)
db_tools_html = match_db.group(0) if match_db else ""

# Extract db styles
match_styles = re.search(r'{% block stylesheets %}(.*?){% endblock stylesheets %}', db_content, re.DOTALL)
db_styles = match_styles.group(1) if match_styles else ""

# Insert db_tools into scan_content after <h2 class="mb-4">לוحة التحكم بالمسح</h2>
scan_content = scan_content.replace(
    '<h2 class="mb-4">لوحة التحكم بالمسح</h2>',
    '<h2 class="mb-4">لوحة تحكم الإدارة</h2>\n' + db_tools_html + '\n<hr class="my-5">\n<h2 class="mb-4">لوحة التحكم بالمسح</h2>'
)

# Insert styles
scan_content = scan_content.replace(
    '{% block stylesheets %}',
    '{% block stylesheets %}\n' + db_styles
)

with open("apps/templates/accounts/admin.html", "w", encoding="utf-8") as f:
    f.write(scan_content)

print("Merged successfully")
