import os

import pytz
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = "13o-4nYWkd7REaTWHTOw0MedY9F8TLHYcsWPt9tooZzc"

_raw_uid = os.getenv("ALLOWED_USER_ID", "")
ALLOWED_USER_ID: int | None = int(_raw_uid) if _raw_uid.lstrip('-').isdigit() else None

VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

DEFAULT_CLOSING_DAYS = {
    'VCB JCB': 15,
    'Techcombank': 20,
    'Vietcombank': 20,
    'Shinhan': 10,
    'Kbank': 5,
    'UOB': 15,
}


class TxnCol:
    DATE, CARD, AMOUNT, CATEGORY, TYPE, DESC, MONTH, REFUND = range(8)


class InstCol:
    ITEM, CARD, START, PRICE, PERIODS = range(5)


CATEGORY_KEYBOARD = ReplyKeyboardMarkup(
    [['Food', 'Transport'], ['Personal', 'Home'], ['Subscription', 'Other']],
    one_time_keyboard=True,
    resize_keyboard=True,
)
