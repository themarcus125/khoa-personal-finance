# Telegram Personal Finance Bot

A custom Telegram bot built in Python to seamlessly track expenses and manage installments directly into your **Google Sheets Personal Finance Dashboard**.

---

## ✨ Features

- **Quick Expense Logging** — Add new transactions using an interactive conversation flow right from Telegram.

- **Auto-Calculated Statement Months** — The bot dynamically fetches your credit card closing dates from your Google Sheet settings and automatically calculates the correct Statement Month (e.g., `May-2026`) for every purchase, respecting the Vietnam timezone (`Asia/Ho_Chi_Minh`).

- **Installment Tracking** — Log new installment plans, and the bot will append them perfectly to your sheet.

- **Financial Reporting** — Pull real-time data from your dashboard directly into Telegram:
  - `/dashboard` — Quick overview of this month's cash flow and fixed expenses.
  - `/budget` — 3-month forecast of income, expenses, and budget percentage used.
  - `/closing` — Lists all your cards and exactly how many days until they close.
  - `/report` — A custom calculated sum of your transactions, grouped by statement month.

- **Dynamic Settings** — Update your card names or closing dates in Google Sheets, type `/refresh` in the bot, and the custom Telegram keyboards update instantly.

---

## 🚀 Setup Guide

This bot interacts securely with your personal Google Sheet. Follow these steps to generate the necessary API tokens and get the bot running locally.

### 1. Set up the Telegram Bot

1. Open Telegram and search for **@BotFather**.
2. Send the message `/newbot`.
3. Follow the prompts to name your bot and give it a username.
4. BotFather will provide an **HTTP API Token** (e.g., `123456789:ABCDefghIJKLmnopQRSTuvwxyz`). Keep this safe!

### 2. Set up Google Sheets API Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new **Project** (e.g., `"Personal Finance Bot"`).
3. Search for **Google Sheets API** and click **Enable**.
4. Search for **Google Drive API** and click **Enable**.
5. Navigate to **APIs & Services > Credentials**.
6. Click **Create Credentials** and select **Service account**.
7. Name it `"finance-bot"` and complete the setup.
8. Under **Service Accounts**, click the account you just created.
9. Go to **Keys** tab → **Add Key** → **Create new key** → Select **JSON**.
10. Download the file, open it in a text editor, and copy its entire contents — you'll need this for your `.env` file in Step 4.

### 3. Share your Sheet with the Bot

1. In the downloaded JSON file, locate the `client_email` field (e.g., `finance-bot@your-project.iam.gserviceaccount.com`).
2. Open your **Personal Finance Google Sheet**.
3. Click the **Share** button in the top right.
4. Paste the bot's email address and grant it **Editor** permissions.

### 4. Create your `.env` File

In the same folder as your `finance_bot.py` script, create a file named exactly `.env` and populate it:

```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
GOOGLE_CREDENTIALS_JSON='{"type": "service_account", "project_id": "...", ...}'
ALLOWED_USER_ID="your_telegram_user_id_here"
```

> ⚠️ **Note:** Wrap the Google JSON value in single quotes `''` to prevent parsing errors.

> 🔒 **To find your Telegram user ID**, message [@userinfobot](https://t.me/userinfobot) on Telegram — it will reply with your numeric ID (e.g. `123456789`). The bot will refuse to start if `ALLOWED_USER_ID` is not set.

### 5. Install Dependencies & Run

> Modern Python setups (macOS/Linux) require a **virtual environment** to avoid the `externally-managed-environment` error.

**Create the virtual environment:**
```bash
python3 -m venv venv
```

**Activate it:**
```bash
# Mac/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**Install dependencies:**
```bash
pip install python-telegram-bot gspread python-dateutil pytz python-dotenv
```

**Run the bot:**
```bash
python finance_bot.py
```

> 💡 Every time you reopen your terminal, re-run the activation command before starting the bot.

---

## 🤖 Available Commands

| Command | Description |
|---|---|
| 💸 `/expense` | Start the conversation to add a new transaction |
| 🙏🏼 `/installment` | Start the conversation to add a new installment plan |
| 📈 `/dashboard` | Overview of this month's totals from the Dashboard sheet |
| 💰 `/budget` | View monthly cash flow and budget used for the next 3 months |
| 📅 `/closing` | Check upcoming card statement dates and statuses |
| 📊 `/report` | View a summary of raw transactions grouped by Statement Month |
| 🔄 `/refresh` | Reload settings and card details directly from the Google Sheet |
| ❌ `/cancel` | Abort any current data entry process |

---

## 📝 Usage Notes

- **Installments flow** — Because the Google Sheet uses auto-calculating columns for billing cycles and paid periods (Columns `F` through `M`), the bot will insert your raw purchase data on the left and remind you to open the sheet and drag formulas down from the row above.

- **Transactions sheet** — Entirely automated from start to finish! 🎉