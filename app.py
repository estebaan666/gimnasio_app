import sys
import os
import importlib.util
from flask import Flask

# -----------------------------------------------------------------------------
# PROXY APP.PY FOR RENDER DEPLOYMENT
# -----------------------------------------------------------------------------
# This file sits in the root and proxies requests to the actual Flask app
# located in gimnasio_app/gimnasio_app/app.py.
# It also sets up the python path so internal imports (like 'conexion') work.
# -----------------------------------------------------------------------------

# 1. Add the inner directory to sys.path
#    This allows the inner app to import 'conexion' and other sibling modules.
current_dir = os.path.dirname(os.path.abspath(__file__))
inner_app_dir = os.path.join(current_dir, 'gimnasio_app', 'gimnasio_app')

if os.path.exists(inner_app_dir):
    sys.path.insert(0, inner_app_dir)
    
    try:
        # 2. Import the inner app using importlib to avoid name collision 
        #    (since this file is also named app.py)
        spec = importlib.util.spec_from_file_location("real_app_module", os.path.join(inner_app_dir, "app.py"))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["real_app_module"] = module
            spec.loader.exec_module(module)
            
            # 3. Expose the 'app' object for Gunicorn
            app = module.app
        else:
            raise ImportError("Could not find app.py spec in inner directory")
            
    except Exception as e:
        # Fallback: Minimal app to show error instead of crashing container
        app = Flask(__name__)
        @app.route('/')
        def fallback():
            return f"<h1>Deployment Error</h1><p>Failed to load inner app.</p><pre>{str(e)}</pre>"
else:
    # Fallback: Minimal app if directory structure is wrong
    app = Flask(__name__)
    @app.route('/')
    def fallback():
        return "<h1>Configuration Error</h1><p>Could not find 'gimnasio_app/gimnasio_app' directory.</p>"

if __name__ == '__main__':
    app.run()
