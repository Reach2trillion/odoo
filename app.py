"""Facebook auto-reply bot with Khmer voice responses.

Receives Facebook Page webhook events (Messenger messages and Page
comments), picks a reply from configurable keyword rules, converts the
reply to Khmer speech with Google TTS, and answers the user:

- Messenger messages -> Khmer text + Khmer voice (audio) message
- Page post comments -> Khmer text comment reply

Configuration is done through environment variables (see .env.example)
and the replies.json rule file.
"""

import hashlib
import hmac
import json
import logging
import os
import threading
from pathlib import Path

import requests
from flask import Flask, request
from gtts import gTTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fb-auto-reply")

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")
APP_SECRET = os.environ.get("APP_SECRET", "")
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0")
TTS_LANG = os.environ.get("TTS_LANG", "km")  # km = Khmer
REPLIES_FILE = Path(os.environ.get("REPLIES_FILE", Path(__file__).parent / "replies.json"))
AUDIO_DIR = Path(os.environ.get("AUDIO_DIR", "/data/audio"))
SEND_TEXT_WITH_VOICE = os.environ.get("SEND_TEXT_WITH_VOICE", "true").lower() != "false"
REPLY_TO_COMMENTS = os.environ.get("REPLY_TO_COMMENTS", "true").lower() != "false"

GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
ATTACHMENT_CACHE_FILE = AUDIO_DIR / "attachments.json"

app = Flask(__name__)

_lock = threading.Lock()
_attachment_cache = {}


def _load_attachment_cache():
    global _attachment_cache
    try:
        _attachment_cache = json.loads(ATTACHMENT_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _attachment_cache = {}


def _save_attachment_cache():
    try:
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        ATTACHMENT_CACHE_FILE.write_text(
            json.dumps(_attachment_cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        log.exception("Could not persist attachment cache")


def load_replies():
    try:
        return json.loads(REPLIES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.exception("Could not read replies file %s, using fallback reply", REPLIES_FILE)
        return {
            "rules": [],
            "default_reply": "អរគុណសម្រាប់សាររបស់អ្នក! ក្រុមការងារនឹងឆ្លើយតបក្នុងពេលឆាប់ៗនេះ។",
        }


def pick_reply(text):
    """Return the reply text for an incoming message using keyword rules."""
    config = load_replies()
    haystack = (text or "").lower()
    for rule in config.get("rules", []):
        for keyword in rule.get("keywords", []):
            if keyword and keyword.lower() in haystack:
                return rule.get("reply") or config.get("default_reply", "")
    return config.get("default_reply", "")


def synthesize(text):
    """Convert reply text to a Khmer MP3 file, cached by content hash."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(f"{TTS_LANG}:{text}".encode("utf-8")).hexdigest()
    mp3_path = AUDIO_DIR / f"{digest}.mp3"
    if not mp3_path.exists():
        gTTS(text=text, lang=TTS_LANG).save(str(mp3_path))
        log.info("Synthesized %s voice file %s", TTS_LANG, mp3_path.name)
    return digest, mp3_path


def upload_audio(digest, mp3_path):
    """Upload the MP3 once and reuse the attachment id for later sends."""
    with _lock:
        attachment_id = _attachment_cache.get(digest)
    if attachment_id:
        return attachment_id
    with open(mp3_path, "rb") as fh:
        response = requests.post(
            f"{GRAPH_URL}/me/message_attachments",
            params={"access_token": PAGE_ACCESS_TOKEN},
            data={
                "message": json.dumps(
                    {"attachment": {"type": "audio", "payload": {"is_reusable": True}}}
                )
            },
            files={"filedata": (mp3_path.name, fh, "audio/mpeg")},
            timeout=30,
        )
    response.raise_for_status()
    attachment_id = response.json()["attachment_id"]
    with _lock:
        _attachment_cache[digest] = attachment_id
        _save_attachment_cache()
    return attachment_id


def _send_message(psid, message):
    response = requests.post(
        f"{GRAPH_URL}/me/messages",
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={
            "recipient": {"id": psid},
            "messaging_type": "RESPONSE",
            "message": message,
        },
        timeout=30,
    )
    if not response.ok:
        log.error("Send API error %s: %s", response.status_code, response.text)
    response.raise_for_status()


def send_text(psid, text):
    _send_message(psid, {"text": text})


def send_voice(psid, digest, mp3_path):
    attachment_id = upload_audio(digest, mp3_path)
    _send_message(
        psid,
        {"attachment": {"type": "audio", "payload": {"attachment_id": attachment_id}}},
    )


def reply_to_comment(comment_id, text):
    response = requests.post(
        f"{GRAPH_URL}/{comment_id}/comments",
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={"message": text},
        timeout=30,
    )
    if not response.ok:
        log.error("Comment API error %s: %s", response.status_code, response.text)
    response.raise_for_status()


def handle_messaging_event(event):
    message = event.get("message") or {}
    sender = (event.get("sender") or {}).get("id")
    if not sender or message.get("is_echo"):
        return
    if not message and not event.get("postback"):
        return  # delivery/read receipts etc.
    incoming = message.get("text") or (event.get("postback") or {}).get("payload") or ""
    reply = pick_reply(incoming)
    if not reply:
        return
    log.info("Messenger message from %s: %r -> replying", sender, incoming[:120])
    if SEND_TEXT_WITH_VOICE:
        send_text(sender, reply)
    try:
        digest, mp3_path = synthesize(reply)
        send_voice(sender, digest, mp3_path)
    except Exception:
        log.exception("Voice reply failed, text reply was still sent")
        if not SEND_TEXT_WITH_VOICE:
            send_text(sender, reply)


def handle_feed_change(page_id, change):
    if not REPLY_TO_COMMENTS:
        return
    value = change.get("value") or {}
    if value.get("item") != "comment" or value.get("verb") != "add":
        return
    author_id = (value.get("from") or {}).get("id")
    if author_id == page_id:
        return  # never reply to the page's own comments (avoids loops)
    comment_id = value.get("comment_id")
    if not comment_id:
        return
    reply = pick_reply(value.get("message") or "")
    if not reply:
        return
    log.info("Comment %s: %r -> replying", comment_id, (value.get("message") or "")[:120])
    reply_to_comment(comment_id, reply)


def process_payload(payload):
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            try:
                handle_messaging_event(event)
            except Exception:
                log.exception("Failed to handle messaging event")
        for change in entry.get("changes", []):
            if change.get("field") == "feed":
                try:
                    handle_feed_change(entry.get("id"), change)
                except Exception:
                    log.exception("Failed to handle feed change")


def _valid_signature(req):
    if not APP_SECRET:
        return True
    signature = req.headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(APP_SECRET.encode(), req.get_data(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature[len("sha256="):], expected)


@app.get("/")
def health():
    return {"status": "ok", "service": "facebook-auto-reply", "tts_lang": TTS_LANG}


@app.get("/webhook")
def verify_webhook():
    if (
        request.args.get("hub.mode") == "subscribe"
        and request.args.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return request.args.get("hub.challenge", ""), 200
    return "Verification token mismatch", 403


@app.post("/webhook")
def receive_webhook():
    if not _valid_signature(request):
        log.warning("Rejected webhook call with bad signature")
        return "Invalid signature", 403
    payload = request.get_json(silent=True) or {}
    if payload.get("object") in ("page", "instagram"):
        # Reply in the background so Facebook gets a fast 200 OK.
        threading.Thread(target=process_payload, args=(payload,), daemon=True).start()
    return "EVENT_RECEIVED", 200


_load_attachment_cache()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
