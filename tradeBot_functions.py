import os
from binance.client import Client
from datetime import datetime, timedelta
import time
from itertools import count
import json
import pandas as pd
import operator
from csv import DictWriter

test_net = True

api_key_live = 'getYourOwn'
api_secret_live = 'getYourOwn'

api_key_test = 'getYourOwn'
api_secret_test = 'getYourOwn'

if test_net:
    client = Client(api_key_test, api_secret_test)
    client.API_URL = 'https://testnet.binance.vision/api'

else:
    client = Client(api_key_live, api_secret_live)

PAIR_WITH = 'BTC'
QUANTITY = 0.0001 #0.001
FIATS = ['DOWN', 'UP', 'BTCUAH', 'SUPERBTC']
AMOUNT_TRADE_COINS = 5

coins_bought = {}
coins_bought_file_path = 'coins_bought.json'

with open(coins_bought_file_path,) as file:
    print(json.load(file))

if os.path.isfile(coins_bought_file_path):
    with open(coins_bought_file_path) as file:
        coins_bought = json.load(file)


def get_volume():
    volumes_coins = client.get_ticker()
    dict_volumes = {}
    for coin in volumes_coins:
        if PAIR_WITH in coin['symbol'][3:]:
            dict_volumes[coin['symbol']] = float(coin['quoteVolume'])
    dict_volumes_sorted = dict(sorted(dict_volumes.items(), key=operator.itemgetter(1), reverse=True))
    return list(dict_volumes_sorted)[:10] # 40


def get_price():
    initial_price = {}
    prices = client.get_all_tickers()
    for coin in prices:
        if PAIR_WITH in coin['symbol'] and all(item not in coin['symbol'] for item in FIATS):
            initial_price[coin['symbol']] = {'price': coin['price'], 'time': datetime.now()}
    return initial_price


def get_candles():
    coins = get_volume()
    tech_df = {}
    for coin in coins:
        bars = client.get_historical_klines(coin, Client.KLINE_INTERVAL_1HOUR, "2 day ago UTC")
        for line in bars:
            del line[9:]
            del line[5:8]
        tech_df[coin] = pd.DataFrame(bars, columns=['date', 'open', 'high', 'low', 'close', 'number of trades'])
        tech_df[coin].set_index('date', inplace=True)
        tech_df[coin].index = pd.to_datetime(tech_df[coin].index, unit='ms')
        tech_df[coin]['40sma'] = tech_df[coin].close.rolling(40).mean()
        tech_df[coin]['18sma'] = tech_df[coin].close.rolling(18).mean()
        tech_df[coin]['4sma'] = tech_df[coin].close.rolling(4).mean()
    return tech_df


def get_candles_coins_bought():
    bought_tech_df = {}
    for coin in coins_bought:
        bars = client.get_historical_klines(coin, Client.KLINE_INTERVAL_1HOUR, "2 day ago UTC")
        for line in bars:
            del line[9:]
            del line[5:8]
        bought_tech_df[coin] = pd.DataFrame(bars, columns=['date', 'open', 'high', 'low', 'close', 'number of trades'])
        bought_tech_df[coin].set_index('date', inplace=True)
        bought_tech_df[coin].index = pd.to_datetime(bought_tech_df[coin].index, unit='ms')
        bought_tech_df[coin]['40sma'] = bought_tech_df[coin].close.rolling(40).mean()
        bought_tech_df[coin]['18sma'] = bought_tech_df[coin].close.rolling(18).mean()
        bought_tech_df[coin]['4sma'] = bought_tech_df[coin].close.rolling(4).mean()
    return bought_tech_df


def get_moving_average_crossover():
    tech_df = get_candles()
    bought_tech_df = get_candles_coins_bought()
    coin_list = []
    coin_sell_list = []
    for coin in tech_df:
        if tech_df[coin]['4sma'].iloc[-1] > tech_df[coin]['18sma'].iloc[-1] > tech_df[coin]['40sma'].iloc[-1] and \
                tech_df[coin]['4sma'].iloc[-1] > tech_df[coin]['40sma'].iloc[-1] and coin not in coins_bought:
            coin_list.append(coin)
    for bought_coin in bought_tech_df:
        if bought_tech_df[bought_coin]['4sma'].iloc[-1] < bought_tech_df[bought_coin]['18sma'].iloc[-1]:
            coin_sell_list.append(bought_coin)
    return coin_list, coin_sell_list


test_MA = get_moving_average_crossover()
print(test_MA)


def convert_new_volume():
    crossed_coins, coin_sell_list = get_moving_average_crossover()
    lot_size = {}
    volume = {}
    last_price = get_price()
    if len(crossed_coins) == 0:
        print(f'Not buying any coins now...')
    for coin in crossed_coins:
        try:
            info = client.get_symbol_info(coin)
            step_size = info['filters'][2]['stepSize']
            lot_size[coin] = step_size.index('1') - 1
            if lot_size[coin] < 0:
                lot_size[coin] = 0
        except:
            pass
        volume[coin] = float(QUANTITY / float(last_price[coin]['price']))
        if coin not in lot_size:
            volume[coin] = float('{:.1f}'.format(volume[coin]))
        else:
            volume[coin] = float('{:.{}f}'.format(volume[coin], lot_size[coin]))
    return volume, last_price


def trade():
    volume, last_price = convert_new_volume()
    orders = {}
    for coin in volume:
        if coin not in coins_bought or coins_bought[coin] == None and len(coins_bought) < AMOUNT_TRADE_COINS:
            print(f' preparing to buy {volume[coin]} {coin}')
            if test_net:
                test_order = client.create_test_order(symbol=coin, side='BUY', type='MARKET', quantity=volume[coin])
                print(f'{volume[coin]} {coin} has been bought')
            try:
                buy_limit = client.create_order(symbol=coin, side='BUY', type='MARKET', quantity=volume[coin])
            except Exception as e:
                print(e)
            else:
                orders[coin] = client.get_all_orders(symbol=coin, limit=1)
        else:
            print(f'Not buying {coin}')
    return orders, last_price, volume


def update_portfolio(orders, last_price, volume):
    tech_df = get_candles()
    for coin in orders:
        coins_bought[coin] = {
            'symbol': orders[coin][0]['symbol'],
            'orderid': orders[coin][0]['orderId'],
            'buy_date': datetime.fromtimestamp(orders[coin][0]['time']/1000).strftime('%Y-%m-%d %H:%M:%S'),
            'bought_at': last_price[coin]['price'],
            'volume': volume[coin],
            'bought_SMA40': tech_df[coin]['40sma'].iloc[-1],
            'bought_SMA18': tech_df[coin]['18sma'].iloc[-1],
            'bought_SMA4': tech_df[coin]['4sma'].iloc[-1]}
        with open(coins_bought_file_path, 'w') as file:
            json.dump(coins_bought, file, indent=4)


def sell_coins():
    bought_tech_df = get_candles_coins_bought()
    crossed_coins, coin_sell_list = get_moving_average_crossover()
    order_sold = {}

    for coin in coin_sell_list:
        if coin in coin_sell_list:
            print(f"Selling {coins_bought[coin]['volume']} {coin}")
            if test_net:
                test_order = client.create_test_order(symbol=coin, side='SELL', type='MARKET', quantity=coins_bought[coin]['volume'])
            try:
                sell_coins_limit = client.create_order(symbol=coin, side='SELL', type='MARKET', quantity=coins_bought[coin]['volume'])
            except Exception as e:
                print(e)
            else:
                with open('backlog_df.csv', 'a+', newline='') as csv_file:

                    field_names = ['symbol', 'orderid', 'buy_date', 'bought_at', 'volume', 'order_sell_id', 'sold_at', 'sold_date','bought_SMA40', 'bought_SMA18', 'bought_SMA4', 'sold_SMA40', 'sold_SMA18', 'sold_SMA4', 'type']
                    dict_writer = DictWriter(csv_file, fieldnames=field_names)
                    order_sold[coin] = client.get_all_orders(symbol=coin, limit=1)
                    coins_bought[coin].update({'order_sell_id': order_sold[coin][0]['orderId']})
                    coins_bought[coin].update({'sold_at': last_price[coin]['price']})
                    coins_bought[coin].update({'sold_date': datetime.fromtimestamp(order_sold[coin][0]['time']/1000).strftime('%Y-%m-%d %H:%M:%S')})
                    coins_bought[coin].update({'sold_SMA40': bought_tech_df[coin]['40sma'].iloc[-1]})
                    coins_bought[coin].update({'sold_SMA18': bought_tech_df[coin]['18sma'].iloc[-1]})
                    coins_bought[coin].update({'sold_SMA4': bought_tech_df[coin]['4sma'].iloc[-1]})
                    coins_bought[coin].update({'type': order_sold[coin][0]['side']})

                    # testing
                    coins_bought[coin].update({'price_sold': order_sold[coin][0]['price']})
                    dict_writer.writerow(coins_bought[coin])

                del coins_bought[coin]
                with open(coins_bought_file_path, 'w') as file:
                    json.dump(coins_bought, file, indent=4)

    if len(coin_sell_list) == 0:
        for coins in coins_bought:
            print(f'Not selling {coins} for now...')


for i in count():
    orders, last_price, volume = trade()
    update_portfolio(orders, last_price, volume)
    time.sleep(10)
    sell_coins()
    print(f'Please wait until next update ' + str((datetime.now() + timedelta(hours=1)).strftime('%H:%M')))
    time.sleep(3600)
