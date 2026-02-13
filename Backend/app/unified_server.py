
import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 1. Setup Paths to import sibling modules
current_dir = os.path.dirname(os.path.abspath(__file__)) # Backend/app
project_root = os.path.dirname(os.path.dirname(current_dir)) # Resume-Screening-Agent

# Add project root to sys.path so we can find 'JD_Generator'
sys.path.append(project_root)

# 2. Import Both Apps
from .main import app as resume_app

# Import JD Generator App
# We need to act like we are inside JD_Generator for its internal imports to work
# This is tricky because JD_Generator.backend.main imports 'agent' which expects to be in path
jd_backend_path = os.path.join(project_root, "JD_Generator", "backend")
sys.path.append(jd_backend_path)

try:
    from JD_Generator.backend.main import app as jd_app
except ImportError:
    # Fallback if direct import fails due to package structure
    # We dynamically import the module file
    import importlib.util
    spec = importlib.util.spec_from_file_location("jd_main", os.path.join(jd_backend_path, "main.py"))
    jd_module = importlib.util.module_from_spec(spec)
    sys.modules["jd_main"] = jd_module
    spec.loader.exec_module(jd_module)
    jd_app = jd_module.app

# 3. Create Unified App
app = FastAPI(title="Unified RecruitAI Server")

# CORS (Global)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Mount Sub-Applications
# Resume App (Main) -> / (Root)
app.mount("/resume", resume_app) # Optional specific mount
# But since resume_app handles /analyze at root, checking if we can merge routes or mount.
# Best practice: Mount resume app at root for backward compatibility, 
# BUT FastAPI mounts match prefixes. If we mount at root, it catches everything.
# So we mount JD first at specific path.

app.mount("/jd-api", jd_app)

# Mount JD Generator Frontend
jd_frontend_path = os.path.join(project_root, "JD_Generator", "frontend")
if os.path.exists(jd_frontend_path):
    app.mount("/jd-tools", StaticFiles(directory=jd_frontend_path, html=True), name="jd_frontend")
    print(f"✅ JD Frontend mounted at /jd-tools (Path: {jd_frontend_path})")
else:
    print(f"⚠️ Warning: JD Frontend path not found: {jd_frontend_path}")

# Explicitly Mount Reports Directory (Fix for PDF Links)
reports_dir = os.path.join(current_dir, "Reports") # Backend/app/../Reports -> Backend/Reports actually?
# wait, current_dir is Backend/app. We want Backend/Reports usually?
# Let's check main.py line 47: os.makedirs("Reports"). This creates ./Reports relative to CWD.
# If running form Backend root, it is Backend/Reports.
reports_path = os.path.abspath("Reports") 
if not os.path.exists(reports_path): os.makedirs(reports_path)
app.mount("/reports", StaticFiles(directory=reports_path), name="reports")
print(f"✅ Reports mounted at /reports (Path: {reports_path})")

# Mount Resume App Routes specifically or Just Include Router?
app.mount("/", resume_app)

print("✅ Unified Server Started: Resume Agent on / + JD Generator on /jd-api")
