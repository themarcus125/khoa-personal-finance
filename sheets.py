import json
import logging
import os

import gspread
from dateutil.relativedelta import relativedelta
from telegram import ReplyKeyboardMarkup

import config

logger = logging.getLogger(__name__)

# Mutable in-place so any module that does `from sheets import CLOSING_DAYS_CACHE`
# always holds a reference to the live dict.
CLOSING_DAYS_CACHE: dict[str, int] = {}


def get_sheet():
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not creds_json_str:
        logger.error("GOOGLE_CREDENTIALS_JSON environment variable is missing.")
        raise ValueError("Please set the GOOGLE_CREDENTIALS_JSON environment variable.")
    creds_dict = json.loads(creds_json_str)
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds_dict)
    return gc.open_by_key(config.SPREADSHEET_ID)


def load_settings() -> None:
    try:
        sh = get_sheet()
        ws = sh.worksheet("Settings")
        data = ws.get_all_values()
        new_days = {}
        for row in data:
            if len(row) >= 2:
                card_name = str(row[0]).strip()
                closing_day_str = str(row[1]).strip()
                if closing_day_str.isdigit():
                    new_days[card_name] = int(closing_day_str)

        if new_days:
            CLOSING_DAYS_CACHE.clear()
            CLOSING_DAYS_CACHE.update(new_days)
            logger.info(f"Loaded closing days from sheet: {CLOSING_DAYS_CACHE}")
        else:
            logger.warning("No closing days found in 'Settings' sheet. Using defaults.")
            CLOSING_DAYS_CACHE.clear()
            CLOSING_DAYS_CACHE.update(config.DEFAULT_CLOSING_DAYS)
    except Exception:
        logger.exception("Error loading settings")
        if not CLOSING_DAYS_CACHE:
            CLOSING_DAYS_CACHE.update(config.DEFAULT_CLOSING_DAYS)


def get_card_keyboard() -> ReplyKeyboardMarkup:
    cards = list(CLOSING_DAYS_CACHE.keys()) or list(config.DEFAULT_CLOSING_DAYS.keys())
    keyboard = [cards[i : i + 2] for i in range(0, len(cards), 2)]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)


def calculate_statement_month(date_obj, card: str) -> str:
    closing_day = CLOSING_DAYS_CACHE.get(card, 20)
    if date_obj.day > closing_day:
        statement_date = date_obj + relativedelta(months=1)
    else:
        statement_date = date_obj
    return statement_date.strftime("%b-%Y")
