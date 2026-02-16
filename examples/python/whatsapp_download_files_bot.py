from os.path import abspath
from pprint import pprint

import requests
from flask import Flask
from flask import request
from urllib.parse import urlparse
import socket
import ipaddress

app = Flask(__name__)


def is_url_safe(client_url: str) -> bool:
    """
    Basic SSRF protection: only allow http/https URLs whose resolved IPs are not
    private, loopback, link-local, or otherwise non-routable.
    """
    try:
        parsed = urlparse(client_url)
    except Exception:
        return False

    if not parsed.scheme or not parsed.netloc:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    try:
        addrinfo_list = socket.getaddrinfo(hostname, None)
    except OSError:
        return False

    for family, _, _, _, sockaddr in addrinfo_list:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        ):
            return False

    return True


def send_message(chat_id, text):
    """
    Send message to chat_id.
    :param chat_id: Phone number + "@c.us" suffix - 1231231231@c.us
    :param text: Message for the recipient
    """
    # Send a text back via WhatsApp HTTP API
    response = requests.post(
        "http://localhost:3000/api/sendText",
        json={
            "chatId": chat_id,
            "text": text,
            "session": "default",
        },
    )
    response.raise_for_status()

def send_seen(chat_id, message_id, participant):
    response = requests.post(
        "http://localhost:3000/api/sendSeen",
        json={
            "session": "default",
            "chatId": chat_id,
            "messageId": message_id,
            "participant": participant,
        },
    )
    response.raise_for_status()

@app.route("/")
def whatsapp_echo():
    return "WhatsApp Download Files Bot is ready!"


@app.route("/bot", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        return "WhatsApp Download Files Bot is ready!"

    data = request.get_json()
    pprint(data)
    if data["event"] != "message":
        # We can't process other event yet
        return f"Unknown event {data['event']}"

    payload = data["payload"]
    # Ignore messages without files
    if not payload.get("mediaUrl", None):
        return "No files in the message"

    # Number in format 791111111@c.us
    chat_id = payload["from"]
    # Message ID - false_11111111111@c.us_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    message_id = payload['id']
    # For groups - who sent the message
    participant = payload.get('participant')
    # IMPORTANT - Always send seen before sending new message
    if not is_url_safe(client_url):
        error_text = "Received an invalid or unsafe media URL; file was not downloaded."
        print(error_text, client_url)
        send_message(chat_id=chat_id, text=error_text)
        return "Invalid media URL"

    send_seen(chat_id=chat_id, message_id=message_id, participant=participant)

    # Download the file and download it to the current folder
    client_url = payload["mediaUrl"]
    filename = client_url.split("/")[-1]
    path = abspath("./" + filename)
    r = requests.get(client_url)
    with open(path, "wb") as f:
        f.write(r.content)

    # Send a text back via WhatsApp HTTP API
    text = f"We have downloaded file here: {path}"
    print(text)
    send_message(chat_id=chat_id, text=text)

    # Send OK back
    return "OK"
