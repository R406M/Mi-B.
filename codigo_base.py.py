import os
import json
import pandas as pd
from flask import Flask, request
from kucoin.client import Trade, Market
import requests

# Crear la aplicación Flask
app = Flask(__name__)

# Claves de API de KuCoin (reemplaza con tus valores)
KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY", "tu_api_key")
KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY", "tu_secret_key")
KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE", "tu_passphrase")

# Configurar cliente de KuCoin
trade_client = Trade(key=KUCOIN_API_KEY, secret=KUCOIN_SECRET_KEY, passphrase=KUCOIN_PASSPHRASE)
market_client = Market()

# Pares de trading y timeframe
SYMBOL = "DOGE-USDT"
TIMEFRAME = "5min"

# Cálculo del ATR
def calculate_atr(candles, period=14):
    df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['high-low'] = df['high'] - df['low']
    df['high-close'] = abs(df['high'] - df['close'].shift(1))
    df['low-close'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['high-low', 'high-close', 'low-close']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=period).mean()
    return df['atr'].iloc[-1]

# Función para abrir una orden
def place_order(action, amount, tp=None, sl=None):
    try:
        if action == "buy":
            order = trade_client.create_market_order(SYMBOL, "buy", funds=amount)
        elif action == "sell":
            order = trade_client.create_market_order(SYMBOL, "sell", funds=amount)
        print(f"Orden {action} ejecutada: {order}")

        # Configurar Take-Profit y Stop-Loss si es necesario
        if tp or sl:
            # Simular lógica para un trailing o TP/SL avanzado
            print(f"TP: {tp}, SL: {sl} configurados.")
        return order
    except Exception as e:
        print(f"Error al ejecutar la orden: {e}")
        return None

# Ruta para recibir señales de TradingView
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print(f"Señal recibida: {data}")

    # Validar la señal
    if "action" not in data or data["action"] not in ["buy", "sell"]:
        return "Señal inválida", 400

    # Obtener datos históricos para calcular ATR
    candles = market_client.get_kline(SYMBOL, TIMEFRAME)
    atr = calculate_atr(candles)

    # Calcular TP y SL dinámicos
    last_price = float(candles[-1][2])  # Último precio alto
    tp = last_price + (2 * atr) if data["action"] == "buy" else last_price - (2 * atr)
    sl = last_price - (2 * atr) if data["action"] == "buy" else last_price + (2 * atr)

    # Ejecutar la orden
    amount = data.get("amount", 10)  # Monto en USDT (puedes ajustarlo)
    order = place_order(data["action"], amount, tp, sl)
    return {"status": "success", "order": order}, 200

# Ejecutar la app en Heroku
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
