import re

# Leer archivo
with open('scrapers/housing_scraper.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazar todas las ocurrencias
pattern = r"if location_elem else \(location or ['\"]España['\"]\)"
replacement = 'if location_elem else "no especificada"'

content_new = re.sub(pattern, replacement, content)

# Contar cambios
changes = len(re.findall(pattern, content))
print(f"Cambios realizados: {changes}")

# Guardar
with open('scrapers/housing_scraper.py', 'w', encoding='utf-8') as f:
    f.write(content_new)

print("✅ Archivo actualizado")
