import os
import re

backend_dir = r"c:\Users\rafae\Documents\gatein\gatein-server\app"
frontend_dir = r"c:\Users\rafae\Documents\gatein\gatein-app"

replacements = {
    r'"SCHEDULED"': '"ACTIVE"',
    r"'SCHEDULED'": "'ACTIVE'",
    r'"CHECKED_IN"': '"CHECKED-IN"',
    r"'CHECKED_IN'": "'CHECKED-IN'",
    r'"IN_PROGRESS"': '"ON_GOING"',
    r"'IN_PROGRESS'": "'ON_GOING'",
    r'"DESATIVADO"': '"DEACTIVATED"',
    r"'DESATIVADO'": "'DEACTIVATED'",
}

for root, dirs, files in os.walk(backend_dir):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            for old, new in replacements.items():
                content = re.sub(old, new, content)
            
            content = content.replace('"FINALIZADO", ', '')
                
            if original != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Updated {path}")

# Frontend replacements
for root, dirs, files in os.walk(frontend_dir):
    if 'node_modules' in root or '.git' in root or 'android' in root or 'ios' in root:
        continue
    for file in files:
        if file.endswith(('.js', '.jsx')):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            for old, new in replacements.items():
                content = re.sub(old, new, content)
                
            if original != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Updated frontend {path}")
