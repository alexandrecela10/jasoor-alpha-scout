# Gmail Setup for Email Reports

To enable the "Send Email" feature in Alpha Scout, you need to generate a Gmail App Password.

## Why App Password?

Google requires **App Passwords** for third-party apps (like Alpha Scout) to send emails on your behalf. Your regular Gmail password won't work.

## Step-by-Step Setup

### 1. Enable 2-Factor Authentication (Required)

App Passwords only work if 2FA is enabled on your Google account.

1. Go to https://myaccount.google.com/security
2. Under "Signing in to Google", click **2-Step Verification**
3. Follow the prompts to enable 2FA (SMS or authenticator app)

### 2. Generate App Password

1. Go to https://myaccount.google.com/apppasswords
2. You may need to sign in again
3. Under "Select app", choose **Mail**
4. Under "Select device", choose **Other (Custom name)**
5. Enter: `Alpha Scout`
6. Click **Generate**
7. Google will show a 16-character password like: `abcd efgh ijkl mnop`

### 3. Add to Your `.env` File

Copy the 16-character password (remove spaces) and add to your `.env`:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
```

**Important:** Use the App Password, NOT your regular Gmail password!

### 4. Test It

1. Run Alpha Scout: `streamlit run app.py`
2. Complete a search
3. Scroll to "Export & Share" section
4. Enter a recipient email
5. Click "📧 Send Email"

You should see: ✅ Email sent successfully!

## Troubleshooting

| Error | Solution |
|-------|----------|
| **Authentication failed** | Make sure you're using the App Password, not your regular password |
| **2-Step Verification required** | Enable 2FA first at https://myaccount.google.com/security |
| **Connection timeout** | Check your internet connection and firewall settings |
| **App Password not available** | Your organization may have disabled App Passwords - contact IT |

## Security Notes

- App Passwords bypass 2FA, so keep your `.env` file secure
- Never commit `.env` to Git (it's in `.gitignore`)
- Revoke App Passwords you're not using at https://myaccount.google.com/apppasswords
- Each app should have its own unique App Password

## Alternative: Use a Different Email Provider

If you can't use Gmail, update your `.env` with your provider's SMTP settings:

```bash
# Example: Outlook
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your-email@outlook.com
SMTP_PASSWORD=your-password

# Example: Custom SMTP
SMTP_HOST=mail.yourcompany.com
SMTP_PORT=587
SMTP_USER=your-email@yourcompany.com
SMTP_PASSWORD=your-password
```
