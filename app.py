
from flask import Flask, request, jsonify
import time, hmac, hashlib, requests, os, json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Bitunix API 設定
API_KEY = os.getenv("BITUNIX_API_KEY")
API_SECRET = os.getenv("BITUNIX_API_SECRET")
BASE_URL = "https://fapi.bitunix.com"

# Google Sheets 認證：從環境變數 GOOGLE_CREDS 讀取 JSON 字串
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS")
if GOOGLE_CREDS is None:
    raise ValueError("GOOGLE_CREDS 環境變數未設定")
creds_dict = json.loads(GOOGLE_CREDS)

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
SHEET = gspread.authorize(CREDS).open("Bitunix_Trades").sheet1

# 下單函數
def place_order(side, qty=0.1, symbol="BTCUSDT", leverage=20):
    timestamp = int(time.time() * 1000)
    path = "/api/v1/private/futures/order/place"
    url = BASE_URL + path
    data = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "leverage": leverage,
        "open_type": "ISOLATED",
        "position_side": side,
        "quantity": str(qty),
        "timestamp": timestamp
    }
    sign_payload = "&".join([f"{k}={data[k]}" for k in sorted(data)])
    signature = hmac.new(API_SECRET.encode(), sign_payload.encode(), hashlib.sha256).hexdigest()
    headers = {
        "ApiKey": API_KEY,
        "Request-Time": str(timestamp),
        "Signature": signature,
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

# 寫入 Google Sheet
def log_to_sheet(side, result):
    ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    order_id = result.get("data", {}).get("order_id", "N/A")
    status = result.get("msg", "no_response")
    SHEET.append_row([ts, side, order_id, status])

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_data(as_text=True)
    if "LONG" in data:
        res = place_order("BUY")
        log_to_sheet("BUY", res)
        return jsonify(res)
    elif "SHORT" in data:
        res = place_order("SELL")
        log_to_sheet("SELL", res)
        return jsonify(res)
    else:
        return jsonify({"error": "未知訊號"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
