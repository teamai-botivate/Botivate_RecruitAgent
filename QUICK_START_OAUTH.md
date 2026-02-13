# Quick Start - Gmail OAuth Setup

## 🚀 TL;DR - Start Testing in 5 Minutes

### Step 1: Start Backend (1 min)
```powershell
cd c:\Users\prabh\Desktop\Resume-Screening-Agent\Backend
uvicorn app.unified_server:app --reload
```
✅ Should see: `Uvicorn running on http://127.0.0.1:8000`

### Step 2: Open Frontend (30 sec)
- Double-click: `c:\Users\prabh\Desktop\Resume-Screening-Agent\Frontend\index.html`
- OR use your browser to open the file

### Step 3: Connect Gmail (2 min)
1. ✅ Check the "Enable Gmail Sync" toggle
2. 🔗 Click "Connect Gmail" button
3. 🔐 Sign in with your Gmail account
4. ✔️ Click "Allow" on the permission screen
5. ✅ See success message with your email

### Step 4: Test It! (1 min)
1. 📅 Select date range (e.g., last 7 days)
2. 📝 Paste a job description
3. 🚀 Click "Initiate AI Screening"
4. ✨ Watch resumes get fetched from Gmail automatically!

---

## 📊 Visual Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INTERFACE                          │
│                                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │  [✓] Enable Gmail Sync                           │      │
│  │                                                    │      │
│  │  ┌────────────────────────────────────────────┐  │      │
│  │  │  🔗 Not Connected  [Connect Gmail]         │  │      │
│  │  └──────────────────────────────────────▲─────┘  │      │
│  │                                          │        │      │
│  │  From: [2026-02-06]  To: [2026-02-13]   │        │      │
│  └──────────────────────────────────────────┼───────┘      │
│                                              │               │
└──────────────────────────────────────────────┼──────────────┘
                                               │
                    Click "Connect Gmail"      │
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    OAUTH POPUP WINDOW                        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  🔐 Sign in with Google                            │    │
│  │                                                     │    │
│  │  Email: your-email@gmail.com                       │    │
│  │  Password: ••••••••••                              │    │
│  │                                                     │    │
│  │  RecruitAI wants to:                               │    │
│  │  • Read your email messages                        │    │
│  │                                                     │    │
│  │  [Cancel]  [Allow] ◄─── Click this!               │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────────────────────────┬──────────────┘
                                               │
                       Store token             │
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND SERVER                            │
│                                                              │
│  Backend/tokens/                                            │
│  └── default_company_token.pickle  ✅ Created!              │
│                                                              │
└──────────────────────────────────────────────┬──────────────┘
                                               │
                  Status updates automatically  │
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      USER INTERFACE                          │
│                                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │  [✓] Enable Gmail Sync                           │      │
│  │                                                    │      │
│  │  ┌────────────────────────────────────────────┐  │      │
│  │  │  ✅ your-email@gmail.com  [Disconnect]    │  │      │
│  │  └────────────────────────────────────────────┘  │      │
│  │                                                    │      │
│  │  Connected! ✅ Ready to fetch resumes!           │      │
│  └──────────────────────────────────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 What Happens When You Click "Analyze"?

```
1. Frontend sends request to /analyze
         ↓
2. Backend checks: Is Gmail connected?
         ↓
   ✅ Yes → Continue
   ❌ No  → Error: "Please connect Gmail first"
         ↓
3. Backend fetches emails from Gmail
   Query: "has:attachment after:2026-02-06 before:2026-02-13"
         ↓
4. Extract PDF/TXT attachments
   ✅ resume1.pdf
   ✅ resume2.pdf
   ✅ resume3.pdf
         ↓
5. Save to temp folder with [Gmail] prefix
   [Gmail] resume1.pdf
   [Gmail] resume2.pdf
   [Gmail] resume3.pdf
         ↓
6. Run through AI screening pipeline
   (Same process as manual uploads!)
         ↓
7. Generate scored results
         ↓
8. Display in UI
   Rank #1: John Doe (92%) - [Gmail] resume1.pdf
   Rank #2: Jane Smith (87%) - [Gmail] resume2.pdf
   ...
```

---

## 🔧 Troubleshooting (Common Issues)

### Issue: "Gmail not connected" error
**Fix:** Click "Connect Gmail" button first!

### Issue: OAuth popup doesn't open
**Fix:** Check if browser is blocking popups. Allow popups for localhost.

### Issue: "Access blocked: App not verified"
**Fix:** 
1. Go to Google Cloud Console
2. OAuth Consent Screen
3. Add your email to "Test Users"

### Issue: No resumes found
**Fix:**
- Verify you have emails with attachments in that date range
- Check Gmail directly: Search "has:attachment after:2026-02-06"

### Issue: Server not starting
**Fix:**
```powershell
# Install dependencies
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

# Try again
uvicorn app.unified_server:app --reload
```

---

## 📋 Checklist

Before you start:
- [ ] Backend server is running (port 8000)
- [ ] Frontend is open in browser
- [ ] You have test emails with resume attachments in your Gmail
- [ ] Your email is added as Test User in Google Cloud Console

While testing:
- [ ] "Connect Gmail" opens popup
- [ ] After approval, status shows your email
- [ ] Date range is selected
- [ ] JD is pasted/uploaded
- [ ] "Initiate AI Screening" is clicked

Success indicators:
- [ ] Backend logs show: "Fetching Resumes from Gmail..."
- [ ] Backend logs show: "✅ Fetched X resumes from Gmail"
- [ ] Results show [Gmail] prefixed resumes
- [ ] All resumes are scored correctly

---

## 🎉 You're Ready!

If you've completed the checklist, you're all set to test!

**For detailed testing:** See `OAUTH_TESTING_GUIDE.md`
**For implementation details:** See `OAUTH_IMPLEMENTATION_SUMMARY.md`

**Need help?**
- Check backend logs: `Backend/backend.log`
- Check browser console: Press F12 → Console tab

**Happy Testing! 🚀**
