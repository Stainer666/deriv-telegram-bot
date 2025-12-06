import telebot
import websocket
import threading
import json
import time
import random
from collections import deque, Counter

# ======================
# 🔧 CONFIGURATION wghIkCZO2P48QI6
# ======================
BOT_TOKEN = "7970173851:AAG7FWhGY0CTy5i1EA51FAoVSnEzVXCo1Jo"
bot = telebot.TeleBot(BOT_TOKEN)

ADMIN_USERNAME = "@volatilitymindster123456789"
BOT_PASSWORD = "us"

user_sessions = {}
authorized_users = set()

# ======================
# ⚙️ DERIV CLIENT
# ======================

class DerivClient:
    def __init__(self, user_id, api_token):
        self.user_id = user_id
        self.api_token = api_token
        self.ws = None
        self.connected = False
        self.market = "1HZ100V"
        self.authorized = False

        # Trading logic
        self.contract_type = "DIGITDIFF"
        self.base_stake = 1
        self.martingale_stake = 14
        self.current_stake = self.base_stake
        self.last_trade_id = None
        self.last_result = None

        # Prediction logic
        self.ticks = []
        self.memory = deque(maxlen=300)
        self.prediction_round = 0
        self.waiting_contract = False

    # --------------------
    # CONNECTION HANDLERS
    # --------------------
    def connect(self):
        try:
            self.ws = websocket.WebSocketApp(
                "wss://ws.derivws.com/websockets/v3?app_id=1089",
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            threading.Thread(target=self.ws.run_forever, daemon=True).start()
        except Exception as e:
            bot.send_message(self.user_id, f"⚠️ Connection error: {str(e)}")

    def on_open(self, ws):
        bot.send_message(self.user_id, "🔐 Connecting to Deriv...")
        self.authorize()

    def on_message(self, ws, message):
        data = json.loads(message)

        # ✅ Authorization handler
        if data.get("msg_type") == "authorize":
            if "error" in data:
                bot.send_message(self.user_id, f"❌ Authorization failed: {data['error']['message']}")
            else:
                self.authorized = True
                bot.send_message(self.user_id, f"✅ Authorized as {data['authorize']['loginid']}")
                self.subscribe_ticks()

        # ✅ Tick handler
        elif data.get("msg_type") == "tick":
            quote = float(data["tick"]["quote"])
            last_digit = int(str(quote)[-1])

            if 0 <= last_digit <= 9:
                self.ticks.append(last_digit)
                self.memory.append(last_digit)

            epoch = time.strftime('%H:%M:%S', time.localtime(data["tick"]["epoch"]))
            bot.send_message(self.user_id, f"📊 {self.market} | {epoch} | {quote} | digit={last_digit}")

            # Every 30 ticks → make prediction and trade
            if len(self.ticks) >= 30:
                self.prediction_round += 1
                self.make_prediction()
                self.ticks = []

        # ✅ Contract proposal response
        elif data.get("msg_type") == "proposal":
            if "error" in data:
                bot.send_message(self.user_id, f"⚠️ Proposal error: {data['error']['message']}")
            else:
                contract_id = data["proposal"]["id"]
                self.last_trade_id = contract_id
                self.buy_contract(contract_id)

        # ✅ Buy response
        elif data.get("msg_type") == "buy":
            if "error" in data:
                bot.send_message(self.user_id, f"❌ Buy error: {data['error']['message']}")
            else:
                contract_id = data["buy"]["contract_id"]
                self.waiting_contract = True
                bot.send_message(self.user_id, f"📥 Bought contract ID: {contract_id}")

        # ✅ Contract update
        elif data.get("msg_type") == "proposal_open_contract":
            if data["proposal_open_contract"].get("is_sold"):
                profit = float(data["proposal_open_contract"]["profit"])
                self.handle_result(profit)

    def on_error(self, ws, error):
        bot.send_message(self.user_id, f"⚠️ WebSocket Error: {str(error)}")

    def on_close(self, ws, *args):
        bot.send_message(self.user_id, "🔴 Connection closed.")

    # --------------------
    # DERIV API ACTIONS
    # --------------------
    def send(self, data):
        try:
            self.ws.send(json.dumps(data))
        except Exception as e:
            bot.send_message(self.user_id, f"⚠️ Send error: {str(e)}")

    def authorize(self):
        self.send({"authorize": self.api_token})

    def subscribe_ticks(self):
        bot.send_message(self.user_id, f"📡 Subscribing to {self.market} ticks...")
        self.send({"ticks": self.market})

    def unsubscribe_ticks(self):
        try:
            self.send({"forget_all": "ticks"})
        except Exception as e:
            bot.send_message(self.user_id, f"⚠️ Unsubscribe error: {str(e)}")

    # --------------------
    # AI-LIKE SIGNAL + TRADE
    # --------------------
    def make_prediction(self):
        """Predict next digit and immediately prepare trade."""
        if not self.ticks:
            return

        short_freq = Counter(self.ticks)
        long_freq = Counter(self.memory)
        combined_score = {d: short_freq[d]*0.7 + long_freq[d]*0.3 for d in range(10)}

        predicted_digit = max(combined_score, key=combined_score.get)
        confidence = (combined_score[predicted_digit] / sum(combined_score.values())) * 100

        bot.send_message(
            self.user_id,
            f"🎯 *Prediction Round {self.prediction_round}:*\n"
            f"Predicted barrier: `{predicted_digit}`\n"
            f"Confidence: `{confidence:.2f}%`\n"
            f"Stake: `${self.current_stake}`\n"
            f"Signal → Executing DIGITDIFF {predicted_digit}",
            parse_mode="Markdown"
        )

        # Send proposal
        self.send({
            "proposal": 1,
            "amount": self.current_stake,
            "basis": "stake",
            "contract_type": "DIGITDIFF",
            "currency": "USD",
            "duration": 1,
            "duration_unit": "t",
            "symbol": self.market,
            "barrier": str(predicted_digit)
        })

    def buy_contract(self, contract_id):
        """Execute trade."""
        self.send({"buy": contract_id, "price": self.current_stake})
        self.send({"proposal_open_contract": 1, "subscribe": 1, "contract_id": contract_id})

    def handle_result(self, profit):
        """Update stake after win/loss."""
        if profit > 0:
            bot.send_message(self.user_id, f"✅ Win! Profit: ${profit}")
            self.current_stake = self.base_stake
        else:
            bot.send_message(self.user_id, f"❌ Loss! Applying Martingale → Next stake: ${self.martingale_stake}")
            self.current_stake = self.martingale_stake
        self.waiting_contract = False


# ======================
# 🧩 TELEGRAM COMMANDS
# ======================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if user_id in authorized_users:
        bot.send_message(user_id, "✅ Already authorized! Use /connect <api_token> to start.")
    else:
        bot.send_message(user_id, f"🔑 Enter your access password.\nAdmin: {ADMIN_USERNAME}")

@bot.message_handler(func=lambda msg: msg.text and msg.chat.id not in authorized_users and not msg.text.startswith("/"))
def handle_password(message):
    if message.text.strip() == BOT_PASSWORD:
        authorized_users.add(message.chat.id)
        bot.send_message(
            message.chat.id,
            "✅ Password accepted!\nUse `/connect <your_api_token>` to link your Deriv account.",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id, f"❌ Wrong password. Contact {ADMIN_USERNAME}.")

@bot.message_handler(commands=['connect'])
def connect_user(message):
    user_id = message.chat.id
    if user_id not in authorized_users:
        bot.send_message(user_id, f"🔒 Enter password first or contact {ADMIN_USERNAME}.")
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "⚠️ Usage: /connect <your_api_token>")
        return
    api_token = parts[1]
    client = DerivClient(user_id, api_token)
    user_sessions[user_id] = client
    client.connect()

@bot.message_handler(commands=['stop'])
def stop_user(message):
    user_id = message.chat.id
    if user_id in user_sessions:
        client = user_sessions[user_id]
        if client.ws:
            client.ws.close()
        del user_sessions[user_id]
        bot.reply_to(message, "🛑 Bot stopped.")
    else:
        bot.reply_to(message, "⚠️ You have no active session.")

# ======================
# 🚀 RUN
# ======================
print("🤖 Deriv DigitDiff Auto-Trading Bot Running...")
bot.infinity_polling()
