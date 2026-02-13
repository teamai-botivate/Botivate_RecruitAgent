# 📧 Gmail OAuth Integration - Complete Testing Guide

## ✅ **Implementation Summary**

The OAuth 2.0 integration has been successfully completed! Here's what was implemented:

### **New Files Created:**
1. `Backend/app/services/gmail_fetch_service.py` - OAuth-based Gmail fetching
2. This testing guide

### **Modified Files:**
1. `Backend/app/main.py` - Updated to use OAuth Gmail service
2. `Frontend/index.html` - Added OAuth connection UI
3. `Frontend/styles.css` - Added OAuth button styling
4. `Frontend/script.js` - Added OAuth flow logic

---

## 🚀 **Testing Steps**

### **Prerequisites**
Before testing, ensure:
- ✅ Google Cloud Console OAuth credentials are set up (from `GMAIL_INTEGRATION_GUIDE.md`)
- ✅ `Backend/client_secret.json` exists with valid OAuth credentials
- ✅ Gmail API is enabled in Google Cloud Console
- ✅ Your email is added as a **Test User** in OAuth consent screen

---

### **Step 1: Start the Backend Server**

1. Open terminal in the backend directory:
   ```powershell
   cd c:\Users\prabh\Desktop\Resume-Screening-Agent\Backend
   ```

2. Activate virtual environment (if you have one):
   ```powershell
   # Example - adjust based on your setup
   .\venv\Scripts\Activate.ps1
   ```

3. Install required dependencies (if not already installed):
   ```powershell
   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
   ```

4. Start the server:
   ```powershell
   # If using unified server
   uvicorn app.unified_server:app --reload

   # OR if using just the resume screening app
   uvicorn app.main:app --reload
   ```

5. **Expected Output:**
   ```
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
   INFO:     Started reloader process
   ```

6. **Verify Backend APIs:**
   Open browser and test these endpoints:
   - http://localhost:8000/auth/gmail/status?company_id=default_company
   - Should return: `{"connected": false, "email": null}`

---

### **Step 2: Open the Frontend**

1. Navigate to frontend directory:
   ```powershell
   cd c:\Users\prabh\Desktop\Resume-Screening-Agent\Frontend
   ```

2. Open `index.html` in your browser:
   - **Option A:** Double-click `index.html`
   - **Option B:** Use Live Server in VS Code
   - **Option C:** Use Python HTTP server:
     ```powershell
     python -m http.server 8080
     # Then open http://localhost:8080
     ```

3. **Expected UI:**
   - You should see the main RecruitAI interface
   - Enable the "Enable Gmail Sync" checkbox
   - Two new sections should appear:
     - **Gmail Connection Status** (with "Not Connected" badge)
     - **Connect Gmail** button
     - **Date range picker**

---

### **Step 3: Connect Gmail Account (OAuth Flow)**

1. **Enable Gmail Sync:**
   - Check the "Enable Gmail Sync" checkbox
   - The OAuth connection section should slide down

2. **Check Connection Status:**
   - On page load, you should see:
     - 🔗 "Not Connected" badge
     - "Connect Gmail" button

3. **Click "Connect Gmail" Button:**
   - A popup window should open
   - You'll be redirected to Google's OAuth consent screen

4. **Google OAuth Flow:**
   
   **a. Sign In (if not already signed in)**
   - Use the Gmail account you want to connect
   - This should be the account you added as a "Test User" in Google Cloud Console

   **b. Consent Screen**
   - **If you see "Google hasn't verified this app" warning:**
     - Click **"Advanced"** → **"Go to RecruitAI (unsafe)"**
     - This is normal for apps in testing mode
   
   - **Grant Permissions:**
     - You'll see: "RecruitAI wants to access your Google Account"
     - **Permission requested:** "View your email messages and settings"
     - Click **"Allow"**

5. **Success Page:**
   - You'll see a success page with:
     - ✅ "Gmail Connected!"
     - Your connected email address
     - "Go to Dashboard" button
   - The popup will auto-close after 2 seconds

6. **Verify Connection:**
   - Back on the main page, the status should update to:
     - ✅ "your-email@gmail.com" (your actual email)
     - Button changes to **"Disconnect"**
   - The status badge should turn green

---

### **Step 4: Test Gmail Resume Fetching**

1. **Prepare Test Data:**
   - Send yourself a few test emails with PDF resume attachments
   - Use your connected Gmail account
   - Send emails within a recent date range (e.g., last 7 days)

2. **Set Date Range:**
   - In the "From" field: Select start date (e.g., 7 days ago)
   - In the "To" field: Select today's date

3. **Add Job Description:**
   - Either:
     - Paste a JD in the text area, OR
     - Upload a JD PDF file

4. **Run Analysis:**
   - Click **"Initiate AI Screening"** button
   - You should see:
     - Loading screen: "Checking Gmail Connection..."
     - Then: "Fetching Resumes from Gmail..."
     - Progress updates in real-time

5. **Monitor Backend Logs:**
   In the terminal where the server is running, you should see:
   ```
   INFO:GmailFetchService - Searching Gmail with query: has:attachment after:2026-02-06 before:2026-02-13
   INFO:GmailFetchService - Found 5 emails with attachments
   INFO:GmailFetchService -   ✅ Extracted: resume1.pdf from 'Job Application - Software Engineer'
   INFO:GmailFetchService -   ✅ Extracted: resume2.pdf from 'Application for Frontend Developer'
   INFO:GmailFetchService - Successfully extracted 3 resume files from Gmail
   ```

6. **Expected Results:**
   - Resumes from Gmail will be prefixed with `[Gmail]` in the report
   - They'll be analyzed alongside any manually uploaded resumes
   - Final results will show all candidates with scores

---

### **Step 5: Test Error Scenarios**

#### **Test 1: Try to Use Gmail Without Connecting**

1. Disconnect Gmail (click "Disconnect" button)
2. Keep "Enable Gmail Sync" checked
3. Select date range
4. Click "Initiate AI Screening"

**Expected:** Error message: "Gmail not connected. Please connect your Gmail account first by clicking 'Connect Gmail' button."

#### **Test 2: Invalid Date Range**

1. Connect Gmail
2. Enable Gmail Sync
3. Leave date fields empty
4. Click "Initiate AI Screening"

**Expected:** Error: "Sync parameters missing: Check date range."

#### **Test 3: No Emails Found**

1. Connect Gmail
2. Set a date range with no emails (e.g., 10 years ago)
3. Run analysis

**Expected:** 
- Backend logs: "No resumes found in Gmail for the specified date range"
- Analysis should proceed with manually uploaded resumes (if any)

---

### **Step 6: Test Disconnect Flow**

1. With Gmail connected, click **"Disconnect"** button
2. Confirm the disconnect prompt
3. **Expected:**
   - Success message: "Gmail disconnected successfully"
   - Status updates to: 🔗 "Not Connected"
   - Button changes back to "Connect Gmail"

4. **Verify Token Deletion:**
   - Check `Backend/tokens/` directory
   - `default_company_token.pickle` should be deleted

---

## 🐛 **Common Issues & Solutions**

### **Issue 1: "client_secret.json not found"**
**Solution:**
- Ensure `client_secret.json` is in `Backend/` directory
- Re-download from Google Cloud Console if needed
- Check file name (must be exactly `client_secret.json`)

### **Issue 2: "Access blocked: App has not completed verification"**
**Solution:**
- Go to Google Cloud Console → OAuth Consent Screen
- Add your email to **Test Users** list
- Make sure the app is in "Testing" mode (not "Production")

### **Issue 3: Popup appears but immediately closes**
**Solution:**
- Check browser console for errors (F12)
- Ensure `redirect_uri` in `client_secret.json` matches your server URL
- Should be: `http://localhost:8000/auth/gmail/callback`

### **Issue 4: "Gmail not connected" error persists after connecting**
**Solution:**
- Check browser console for OAuth completion message
- Refresh the page to trigger status check
- Verify token file exists: `Backend/tokens/default_company_token.pickle`

### **Issue 5: No resumes extracted from Gmail**
**Solution:**
- Verify emails have PDF or TXT attachments
- Check date range includes the emails
- Look at backend logs for email count
- Try with "has:attachment" search in Gmail to verify emails exist

---

## 📊 **Success Criteria**

Your OAuth integration is working correctly if:

✅ **Connection Flow:**
- [x] "Connect Gmail" opens Google OAuth popup
- [x] After granting permission, status updates automatically
- [x] Connected email is displayed in the UI
- [x] Token file is created in `Backend/tokens/`

✅ **Fetching Flow:**
- [x] Gmail resumes are fetched within specified date range
- [x] PDFs and TXTs are extracted from email attachments
- [x] Resumes are labeled with `[Gmail]` prefix
- [x] Backend logs show successful extraction

✅ **Analysis Flow:**
- [x] Gmail resumes are analyzed alongside manual uploads
- [x] Scoring and AI analysis works for Gmail resumes
- [x] Final report includes all resumes
- [x] PDF links work in the results table

✅ **Disconnect Flow:**
- [x] "Disconnect" button revokes access
- [x] Token file is deleted
- [x] Status updates to "Not Connected"
- [x] Can reconnect without issues

---

## 🔒 **Security Notes**

1. **Production Deployment:**
   - Move to a proper database (PostgreSQL/MySQL) instead of pickle files
   - Encrypt tokens at rest using `cryptography` library
   - Use environment variables for OAuth credentials
   - Enable HTTPS for production

2. **Multi-Company Support (Future):**
   - Current implementation uses `default_company` ID
   - To support multiple companies:
     - Add user authentication (JWT/session)
     - Map users to company IDs
     - Update OAuth flow to use dynamic company IDs

3. **Token Management:**
   - Tokens are auto-refreshed when expired
   - Refresh tokens are long-lived (until revoked)
   - Users can revoke access from Google Account settings

---

## 📝 **Next Steps**

After successful testing, you can:

1. **Customize Gmail Search:**
   - Edit `gmail_fetch_service.py` to add more filters
   - Example: Only fetch from specific senders

2. **Add Email Metadata:**
   - Store `email_subject` and `email_body` for better role matching
   - Already implemented in `gmail_fetch_service.py`!

3. **Improve UI:**
   - Add loading state during OAuth
   - Show number of emails found
   - Display email preview in results

4. **Multi-Company Mode:**
   - Add login system
   - Create company management dashboard
   - Store company→email mappings in database

---

## 🎉 **You're All Set!**

If you've completed all tests successfully, your OAuth integration is production-ready for single-company use!

**Questions or Issues?**
- Check backend logs: `Backend/backend.log`
- Check browser console (F12 → Console tab)
- Review `GMAIL_INTEGRATION_GUIDE.md` for Google Cloud setup

**Happy Hiring! 🚀**
