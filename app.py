from flask import Flask, request
import requests
import os
import threading
from collections import defaultdict
from openai import OpenAI

app = Flask(__name__)

ai = OpenAI(
    api_key=os.getenv("GROQ_API_KEY") or "missing",
    base_url="https://api.groq.com/openai/v1",
)
MODEL = "llama-3.3-70b-versatile"

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "jassem_decor_secret_token_2025")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
GRAPH_URL = "https://graph.facebook.com/v21.0/me/messages"

BUSINESS_INFO = """
أنت المساعد الذكي لخدمة الزبائن لصفحة "جاسم للديكور 02" (Jassem Décor 02) في الجزائر.

معلومات المحل والنشاط:
- النشاط: بيع الديكورات المنزلية والحائطية العصرية، المرايات (Miroirs)، الورود والتحف، أشياء الهدايا، المباخر والفواحات والبخور، والعديد من المنتجات الأخرى.
- المكان: الجزائر.
- التوصيل (Livraison): متوفر لـ 58 ولاية (لباب الدار أو للمكتب).
- الدفع (Paiement): الدفع عند الاستلام (تخلص كي يوصلك المنتج).
- طريقة الطلب: لطلب أي منتج، يرسل الزبون: (صورة أو اسم المنتج، الاسم واللقب، رقم الهاتف، الولاية والبلدية).

قواعد التحدث والرد:
1. تحدث بالدارجة الجزائرية المحترمة والمرحبة (مثل: مرحباً بيك خويا / أختي، الله يسلمك، واش تحب تسقسي...).
2. إذا سأل الزبون عن سعر منتج معين، اطلب منه يبعث صورة أو يوضح الموديل اللي حابو لأن الأسعار تختلف حسب النوع والحجم.
3. كن مختصراً ومباشراً ولا تكتب رسائل طويلة جداً.
4. لا تخترع أسعاراً من عندك أبداً.
5. إذا أراد الزبون التحدث مع صاحب المحل، أخبره أنه سيتم تحويل رسالته للإدارة وسيتواصلون معه قريباً.
"""

MAX_HISTORY = 8
conversations = defaultdict(list)
paused_users = set()
processed_mids = set()

@app.route("/", methods=["GET"])
def home():
    return "Jassem Decor 02 Bot is Running Successfully!", 200

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.mode") == "subscribe" and \
       request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def receive():
    data = request.get_json(silent=True) or {}
    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            message = event.get("message")
            if not message or message.get("is_echo"):
                continue

            mid = message.get("mid")
            if mid in processed_mids:
                continue
            processed_mids.add(mid)

            sender_id = event["sender"]["id"]
            text = message.get("text")

            if not text:
                send_message(sender_id, "مرحباً بيك! يعطيك الصحة على الصورة، اكتب لي واش تحب تسقسي على هذا الموديل ونجاوبك.")
                continue

            if sender_id in paused_users:
                continue

            if any(w in text for w in ["مسؤول", "بشري", "انسان", "إنسان", "نيميرو", "هاتف", "تلفون", "مول المحل"]):
                paused_users.add(sender_id)
                send_message(sender_id, "تم تحويل رسالتك لمسؤول المحل، سيتواصل معك في أقرب وقت إن شاء الله.")
                continue

            threading.Thread(target=handle_ai, args=(sender_id, text)).start()

    return "EVENT_RECEIVED", 200

def handle_ai(sender_id, text):
    reply = get_ai_reply(sender_id, text)
    send_message(sender_id, reply)

def get_ai_reply(sender_id, user_text):
    history = conversations[sender_id]
    history.append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": BUSINESS_INFO}]
    messages += history[-MAX_HISTORY:]

    try:
        response = ai.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.6,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        print("AI error:", e)
        reply = "مرحباً بيك أخي/أختي، سمحلنا كاين ضغط خفيف. عاود ابعث رسالتك من فضلك."

    history.append({"role": "assistant", "content": reply})
    return reply

def send_message(recipient_id, text):
    payload = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE",
        "message": {"text": text[:2000]},
    }
    r = requests.post(GRAPH_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload)
    if r.status_code != 200:
        print("Send error:", r.text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
