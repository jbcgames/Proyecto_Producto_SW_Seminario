
import os, requests
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = "8436903007:AAHReCa7ljClXrTThVSW0sk7gkzvEXbwNIM"

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_telegram_message(chat_id: str, text: str) -> bool:
    """Envía un mensaje de texto simple."""
    if not BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN no configurado")
        return False
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        })
        return r.ok
    except Exception as e:
        print("❌ Error enviando texto:", e)
        return False


def send_telegram_photo(chat_id: str, photo_url: str, caption: str | None = None) -> bool:
    """Envía una foto con texto opcional (caption)."""
    if not BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN no configurado")
        return False
    try:
        payload = {"chat_id": chat_id, "photo": photo_url}
        if caption:
            payload["caption"] = caption[:1024]  # límite de 1024 caracteres
        r = requests.post(f"{BASE_URL}/sendPhoto", json=payload)
        return r.ok
    except Exception as e:
        print("❌ Error enviando foto:", e)
        return False
