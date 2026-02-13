
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

# 4. Gmail OAuth Endpoints
from fastapi import HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from .services.gmail_oauth import gmail_oauth_service

@app.get("/auth/gmail/start")
async def start_gmail_oauth(company_id: str = Query(default="default_company")):
    """
    Start Gmail OAuth flow
    
    Args:
        company_id: Unique identifier for the company (default: "default_company" for single-tenant)
    
    Returns:
        Redirect to Google OAuth consent screen
    """
    try:
        # Get the redirect URI (adjust for production)
        redirect_uri = "http://localhost:8000/auth/gmail/callback"
        
        # Generate authorization URL
        auth_url, state = gmail_oauth_service.get_authorization_url(company_id, redirect_uri)
        
        # Redirect user to Google
        return RedirectResponse(url=auth_url)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth: {str(e)}")


@app.get("/auth/gmail/callback")
async def gmail_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    company_id: str = Query(default="default_company")
):
    """
    Handle OAuth callback from Google
    
    Args:
        code: Authorization code from Google
        state: State token for CSRF protection
        company_id: Company identifier
    
    Returns:
        Success page with connection status
    """
    try:
        # Exchange code for tokens
        result = gmail_oauth_service.handle_callback(company_id, code, state)
        
        # Return success page
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Gmail Connected</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 400px;
                }}
                .success-icon {{
                    font-size: 64px;
                    color: #4CAF50;
                }}
                h1 {{
                    color: #333;
                    margin: 20px 0 10px;
                }}
                p {{
                    color: #666;
                    margin: 10px 0;
                }}
                .email {{
                    background: #f5f5f5;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 20px 0;
                    color: #333;
                    font-weight: bold;
                }}
                .btn {{
                    display: inline-block;
                    margin-top: 20px;
                    padding: 12px 30px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                }}
                .btn:hover {{
                    background: #5568d3;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Gmail Connected!</h1>
                <p>{result['message']}</p>
                <div class="email">📧 {result['email']}</div>
                <p>You can now close this window and return to RecruitAI.</p>
                <a href="/" class="btn">Go to Dashboard</a>
            </div>
            <script>
                // Auto-close after 3 seconds and notify parent window
                setTimeout(() => {{
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'gmail_connected',
                            email: '{result['email']}'
                        }}, '*');
                        window.close();
                    }}
                }}, 2000);
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")


@app.get("/auth/gmail/status")
async def gmail_connection_status(company_id: str = Query(default="default_company")):
    """
    Check if Gmail is connected for a company
    
    Returns:
        {"connected": bool, "email": str or null}
    """
    try:
        is_connected = gmail_oauth_service.is_connected(company_id)
        
        email = None
        if is_connected:
            # Get user email
            credentials = gmail_oauth_service.get_credentials(company_id)
            from googleapiclient.discovery import build
            service = build('gmail', 'v1', credentials=credentials)
            profile = service.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress')
        
        return {
            "connected": is_connected,
            "email": email
        }
    
    except Exception as e:
        return {
            "connected": False,
            "email": None,
            "error": str(e)
        }


@app.post("/auth/gmail/disconnect")
async def disconnect_gmail(company_id: str = Query(default="default_company")):
    """
    Disconnect Gmail and revoke access
    
    Returns:
        {"status": "success"}
    """
    try:
        gmail_oauth_service.revoke_access(company_id)
        return {"status": "success", "message": "Gmail disconnected successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disconnect: {str(e)}")


# 5. Mount Sub-Applications
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
