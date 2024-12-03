import ccxt
import pandas as pd
import time
from flask import Flask
from flask import request
from flask import jsonify
import logging

# Configuración del bot
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configuración del exchange
exchange = ccxt.binance({
    'apiKey': 'TU_API_KEY',
    'secret': 'TU_API_SECRET'
})

# Parámetros del bot
atr_period = 14  # Número de períodos para el cálculo del ATR
atr_multiplier_tp = 2  # Multiplicador para el Take-Profit
atr_multiplier_sl = 1  # Multiplicador para el Stop-Loss
positions = {}  # Rastrea posiciones abiertas

# Función para calcular el ATR
def calculate_atr(symbol, timeframe, lookback):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe)
    data = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # Calcular True Range (TR)
    data['high-low'] = data['high'] - data['low']
    data['high-close'] = abs(data['high'] - data['close'].shift(1))
    data['low-close'] = abs(data['low'] - data['close'].shift(1))
    data['TR'] = data[['high-low', 'high-close', 'low-close']].max(axis=1)

    # Calcular Average True Range (ATR)
    data['ATR'] = data['TR'].rolling(window=lookback).mean()

    return data['ATR'].iloc[-1]  # Retorna el último ATR

# Función para abrir una orden con TP y SL dinámicos
def place_order_with_dynamic_tp_sl(signal, symbol, amount):
    global positions

    # Precio actual
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker['last']

    # Calcular ATR
    atr = calculate_atr(symbol, '1h', atr_period)

    # Calcular TP y SL dinámicos
    if signal == 'buy':
        take_profit = current_price + (atr * atr_multiplier_tp)
        stop_loss = current_price - (atr * atr_multiplier_sl)
        order = exchange.create_market_buy_order(symbol, amount)
        positions[symbol] = {'type': 'buy', 'tp': take_profit, 'sl': stop_loss, 'entry': current_price}
    elif signal == 'sell':
        take_profit = current_price - (atr * atr_multiplier_tp)
        stop_loss = current_price + (atr * atr_multiplier_sl)
        order = exchange.create_market_sell_order(symbol, amount)
        positions[symbol] = {'type': 'sell', 'tp': take_profit, 'sl': stop_loss, 'entry': current_price}

    logging.info(f"Orden abierta: {signal.upper()} {symbol}")
    logging.info(f"TP: {take_profit}, SL: {stop_loss}")
    return positions[symbol]

# Función para monitorear posiciones y cerrarlas automáticamente
def monitor_positions():
    global positions

    while True:
        for symbol in list(positions.keys()):
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            position = positions[symbol]

            # Verificar condiciones de cierre
            if position['type'] == 'buy' and (current_price >= position['tp'] or current_price <= position['sl']):
                exchange.create_market_sell_order(symbol, 0.001)  # Cerrar posición
                logging.info(f"Posición cerrada en {symbol}. Precio: {current_price}")
                positions.pop(symbol)
            elif position['type'] == 'sell' and (current_price <= position['tp'] or current_price >= position['sl']):
                exchange.create_market_buy_order(symbol, 0.001)  # Cerrar posición
                logging.info(f"Posición cerrada en {symbol}. Precio: {current_price}")
                positions.pop(symbol)

        time.sleep(10)  # Verificar cada 10 segundos

# Endpoint para recibir señales desde TradingView
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json

    if 'signal' not in data or 'pair' not in data:
        return jsonify({'error': 'Faltan datos en la señal'}), 400

    signal = data['signal']
    pair = data['pair']
    amount = 0.001  # Cantidad fija para operar (ajusta según tus necesidades)

    # Abrir orden con TP y SL dinámicos
    result = place_order_with_dynamic_tp_sl(signal, pair, amount)
    return jsonify({'message': f'Señal procesada: {signal} en {pair}', 'details': result}), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
