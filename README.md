# binance_MA_crossover_tradingBot
TradingBot that trades basis moving average crossovers. 

Currently experimenting different stratagies: 

- def get_volume() returns top most traded coins (in volume). Amount can be adjusted of top traded coins (for example top 10 or top 40).
- def get_candles() returns moving averages. Moving averge 40, 18 and 4. Moving averages can be adjusted to see which strategie is most profitable. 
- def get_moving_average_crossover() return buy and sell singnales. Buy signal: MA 4 > MA 18 > MA 40 and MA 4 > MA 40. Sell signal: MA 4 < MA 18. Can be adjusted to buy or sell ealier or later
- time.sleep(600) at the end of the code can be adjusted. Not realy sure if this is more profitable... 

Created via PyCharm therefore importing few libaries is required. testing alot at this momement, thefore not finsished yet for found the ideal strategie yet. 
