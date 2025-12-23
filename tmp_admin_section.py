from pathlib import Path
text=Path('frontend/templates/admin_panel.html').read_text(encoding='utf-8')
start=text.index('<section class="admin-card" id="admin-migrations"')
end=start+text[start:].index('</section>')+10
print(text[start:end])
