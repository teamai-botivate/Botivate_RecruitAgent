# Gmail Integration Guide for RecruitAI

This guide details the steps to connect your company's Gmail account to the RecruitAI backend for automated resume fetching.

## 1. Create a Google Cloud Project

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Click the project dropdown in the top bar and select **"New Project"**.
3.  Name it `RecruitAI-Gmail` (or similar) and click **Create**.
4.  Once created, select the project from the dropdown.

## 2. Enable the Gmail API

1.  In the sidebar, navigate to **APIs & Services > Library**.
2.  Search for **"Gmail API"**.
3.  Click on it and then click **Enable**.

## 3. Create OAuth Credentials

1.  Navigate to **APIs & Services > Credentials**.
2.  Click **"Configure Consent Screen"**.
    *   **User Type**: Select **External** (unless you are a Google Workspace admin, then Internal is fine).
    *   **App Name**: `RecruitAI ATS`.
    *   **User Support Email**: Your email.
    *   **Developer Contact Info**: Your email.
    *   Click **Save and Continue**.
3.  **Scopes**:
    *   Click **Add or Remove Scopes**.
    *   Search for and select `https://www.googleapis.com/auth/gmail.readonly`.
    *   Click **Update** and then **Save and Continue**.
4.  **Test Users**:
    *   Add the email address of the account you want to read resumes from (e.g., `hiring@yourcompany.com`).
    *   Click **Save and Continue**.
5.  **Create Credentials**:
    *   Go back to the **Credentials** tab.
    *   Click **Create Credentials > OAuth client ID**.
    *   **Application Type**: **Desktop App**.
    *   **Name**: `RecruitAI Desktop Client`.
    *   Click **Create**.
6.  **Download JSON**:
    *   A modal will appear with your Client ID and Secret.
    *   Click **Download JSON**.
    *   **Rename this file to `credentials.json`**.

## 4. Setup in RecruitAI

1.  **Move the File**:
    *   Copy the `credentials.json` file into the `Backend/` folder of the RecruitAI project.
    *   Path: `c:\Users\prabh\Desktop\Resume-Screening-Agent\Backend\credentials.json`.

2.  **Install Dependencies** (If not already installed):
    ```bash
    pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
    ```

## 5. First Run (Authentication)

1.  Start the backend server as usual.
2.  When you trigger a job that uses Gmail Sync (check the box on frontend), the backend terminal will pause.
3.  It will print a URL or try to open a browser window.
4.  **Login**: Sign in with the Google account you added as a Test User.
5.  **Consent**: You might see a "Google hasn't verified this app" warning. Click **Advanced > Go to RecruitAI (unsafe)**.
6.  **Grant Access**: Allow access to view email messages.
7.  **Success**: The authentication flow will complete, and a `token.json` file will be created in the `Backend/` folder. This token stores your login so you don't need to sign in again.

## 6. Troubleshooting

*   **Error: `Project not configured`**: Ensure you enabled the Gmail API in step 2.
*   **Error: `Access blocked: App has not completed the Google verification process`**: Ensure you added your email as a **Test User** in step 3.4.
*   **Token Expired**: If `token.json` stops working, delete it and re-run Step 5 to generate a new one.

---
**Security Note**: Keep `credentials.json` and `token.json` private. Do not commit them to GitHub.
