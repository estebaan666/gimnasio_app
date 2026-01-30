import sys
import os

# Agrega el directorio donde está app.py al path de Python
# La estructura es repo_root/gimnasio_app/gimnasio_app/app.py
base_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(base_dir, 'gimnasio_app', 'gimnasio_app')
sys.path.insert(0, app_dir)

from app import app

if __name__ == "__main__":
    app.run()
