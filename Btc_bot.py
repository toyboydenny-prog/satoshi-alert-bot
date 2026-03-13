import requests
import time
import pandas as pd

TOKEN = "8614914171:AAElZYEbRphaPR7LORaDxX1kNKZfL8qz8-M"

last_update_id = None
subscribers = set()

# Telegram senden
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

def broadcast(text):
    for chat in subscribers:
        send_message(chat, text)

# BTC Preis
def get_price():
    r = requests.get(
        "https://api.binance.com/api/v3/ticker/price",
        params={"symbol": "BTCUSDT"}
    )
    return float(r.json()["price"])

# Klines
def get_klines(interval="1m", limit=100):
    r = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": "BTCUSDT", "interval": interval, "limit": limit}
    )
    return r.json()

# EMA36 Daily
def ema36_daily():
    data = get_klines("1d", 100)

    closes = [float(x[4]) for x in data]
    df = pd.Series(closes)

    ema = df.ewm(span=36).mean().iloc[-1]

    return closes[-1], ema

# 5m Move
def fast_move():
    data = get_klines("1m", 6)

    first = float(data[0][4])
    last = float(data[-1][4])

    change = (last - first) / first * 100

    return last, change

# Funding
def funding_rate():
    r = requests.get(
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        params={"symbol": "BTCUSDT"}
    )

    return float(r.json()["lastFundingRate"]) * 100

# Open Interest
def open_interest():
    r = requests.get(
        "https://fapi.binance.com/fapi/v1/openInterest",
        params={"symbol": "BTCUSDT"}
    )

    return float(r.json()["openInterest"])

# Spot vs Perp Flow
def spot_vs_perp():

    spot = get_klines("1m", 5)
    spot_volume = sum(float(x[5]) for x in spot)

    perp = requests.get(
        "https://fapi.binance.com/fapi/v1/klines",
        params={"symbol": "BTCUSDT", "interval": "1m", "limit": 5}
    ).json()

    perp_volume = sum(float(x[5]) for x in perp)

    total = spot_volume + perp_volume

    if total == 0:
        return "Unknown"

    spot_pct = spot_volume / total * 100
    perp_pct = perp_volume / total * 100

    if spot_pct > 60:
        return f"Spot dominant {spot_pct:.0f}%"

    if perp_pct > 60:
        return f"Perp dominant {perp_pct:.0f}%"

    return "Mixed flow"

# Breakout
def breakout():

    data = get_klines("1m", 20)

    highs = [float(x[2]) for x in data]
    closes = [float(x[4]) for x in data]

    resistance = max(highs[:-1])

    if closes[-1] > resistance:
        return True

    return False

# Signal Score
def signal_score():

    score = 0

    price, ema = ema36_daily()

    _, move = fast_move()

    flow = spot_vs_perp()

    funding = funding_rate()

    if price > ema:
        score += 20

    if abs(move) > 0.5:
        score += 20

    if "Spot dominant" in flow:
        score += 15

    if "Perp dominant" in flow:
        score += 15

    dist = abs(price - ema) / ema * 100

    if dist < 0.2:
        score += 20

    if abs(funding) > 0.01:
        score += 10

    if breakout():
        score += 15

    return score

# Trading Setup
def trading_setup():

    price, ema = ema36_daily()

    score = signal_score()

    flow = spot_vs_perp()

    if score < 70:
        return None

    if price > ema:

        return f"""
BTC LONG SETUP

Preis: {price:.0f}
EMA36: {ema:.0f}

Flow: {flow}

Entry: {price:.0f}
Stop: {price*0.99:.0f}
TP: {price*1.02:.0f}

Signal Score: {score}
"""

    else:

        return f"""
BTC SHORT SETUP

Preis: {price:.0f}
EMA36: {ema:.0f}

Flow: {flow}

Entry: {price:.0f}
Stop: {price*1.01:.0f}
TP: {price*0.98:.0f}

Signal Score: {score}
"""

# Market Übersicht
def market_overview():

    price = get_price()

    _, move = fast_move()

    flow = spot_vs_perp()

    funding = funding_rate()

    oi = open_interest()

    return f"""
BTC MARKET

Preis: {price:.0f}

5m Move: {move:.2f}%

Flow: {flow}

Funding: {funding:.3f}%

Open Interest: {oi:.0f}
"""

# Alerts
def check_alerts():

    price, ema = ema36_daily()

    dist = abs(price - ema) / ema * 100

    if dist < 0.2:
        broadcast(f"BTC EMA36 TEST\nPreis {price:.0f}")

    _, move = fast_move()

    if abs(move) > 1:
        broadcast(f"BTC MOMENTUM ALERT\nMove {move:.2f}%")

    setup = trading_setup()

    if setup:
        broadcast(setup)

# Telegram Updates
def get_updates():

    global last_update_id

    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

    params = {}

    if last_update_id:
        params["offset"] = last_update_id + 1

    r = requests.get(url, params=params)

    return r.json()["result"]

# Telegram Commands
def handle(chat_id, text):

    subscribers.add(chat_id)

    if text == "/start":

        send_message(chat_id,
        "SatoshiAlert PRO\n\n"
        "/price\n"
        "/market\n"
        "/signal")

    if text == "/price":

        send_message(chat_id,
        f"BTC Preis {get_price():.0f}")

    if text == "/market":

        send_message(chat_id,
        market_overview())

    if text == "/signal":

        setup = trading_setup()

        if setup:
            send_message(chat_id, setup)

        else:
            send_message(chat_id,
            "Kein klares Setup")

print("SatoshiAlert PRO läuft...")

last_alert = 0

while True:

    updates = get_updates()

    for update in updates:

        last_update_id = update["update_id"]

        if "message" not in update:
            continue

        chat_id = update["message"]["chat"]["id"]

        text = update["message"].get("text", "")

        handle(chat_id, text)

    if time.time() - last_alert > 60:

        check_alerts()

        last_alert = time.time()

    time.sleep(1)