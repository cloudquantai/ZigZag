from cloudquant.interfaces import Strategy


###############################################################################################
# CQ Lite ZigZag Strategy.
# 
# On Quora Bruno Matos asked the question:
# Considering that prices zigzag, could this trading strategy be profitable in the long-term? 
# Target 1 to 4 ticks, Buy if a 5m candle closes negative, and sell if 5m candle closes. 
# If the candle closes against you, you average the position.
# 
# This was a really interesting question. Will this strategy work. On the surface it sounded 
# likely to work, but I like to see proof. 
#
# This script is my attempt to implement the strategy as asked.
#############################################################################################

class ZigZag1071031(Strategy):
    ########################################################################################
    #
    # high level strategy - start/finish
    #
    ########################################################################################

    # called when the strategy starts (aka before anything else)
    @classmethod
    def on_strategy_start(cls, md, service, account):
        pass

    # called when the strategy finish (aka after everything else has stopped)
    @classmethod
    def on_strategy_finish(cls, md, service, account):
        pass

    ########################################################################################
    #
    # symbol universe
    #
    ########################################################################################

    # note that this doesn't start with "self" because it's a @classmethod
    @classmethod
    def is_symbol_qualified(cls, symbol, md, service, account):
        # Return only the symbols that I am interested in trading or researching.
        #return symbol in ['EBAY', 'HD', 'MSFT', 'SIRI', 'UNP', 'UPS', 'WBA', 'XLE', 'XLF', 'AAPL']
        
        dow30 = service.symbol_list.get_handle("072c1578-08c5-462a-a94e-325b2bf654b6")
        return service.symbol_list.in_list(dow30,symbol)

    # used to load other symbols data not in is_symbol_qualified(). Only used in backtesting
    @classmethod
    def backtesting_extra_symbols(cls, symbol, md, service, account):
        return False

    ########################################################################################
    #
    # start/finish instance related methods
    #
    ########################################################################################

    # used to pass external parameters for each instance (same for values for every instance)
    def __init__(self):  # , **params - if passing in parameters is desired

        self.IsLongPositionOn = False  # do we have a long position on?
        self.IsShortPositionOn = False  # do we have a short position on?
        self.LongQty = 0  # long quantity of our position
        self.long_entry_price = 0  # estimated price of our position
        self.short_entry_price = 0  # estimated price of our position
        self.TargetProfit = 0.02  # target profit
        self.HowLongHeld = 0  # How Many Bars the position has been held.
        self.MaxMinHeld = 5   # Number of minutes to hold a position before checking to see if there should be a reversal
        self.strat_pnl = 0.0
        
        
    # called at the beginning of each instance
    def on_start(self, md, order, service, account):
        # print "OnStart {0}\t{1}\n".format(service.time_to_string(service.system_time), self.symbol)

        # The model requires that we have at least X minutes of bar data prior
        # to checking to see if a bear price flip has occurred. Therefore we
        # need a variable to track this start time.
        self.model_start = md.market_open_time + service.time_interval(minutes=5)
        
        self.filename = "zigzag.csv"
        self.sOutString = "TimeStamp,Signal,Symbol,Open-5,Close-5,Open-1,Close-1"
        service.write_file(self.filename, self.sOutString)

    # if running with an instance per symbol, call when an instance is terminated
    def on_finish(self, md, order, service, account):
        pass

    ########################################################################################
    #
    # timer method
    #
    ########################################################################################

    # called in timer event is received
    def on_timer(self, event, md, order, service, account):
        pass

    ###############################################################
    # Write to log file
    def MyLog(self, service, timestamp, signal, open5, close5, open1, close1):
        self.sOutString = "{},{},{},{},{},{},{}".format(timestamp,
                                               signal,
                                               self.symbol, 
                                               open5,
                                               close5,
                                               open1,
                                               close1)
        service.write_file(self.filename, self.sOutString)
    
    
    
    ########################################################################################
    #
    # market data related methods
    #
    ########################################################################################

    # called every minute before the first on_trade of every new minute, or 5 seconds after a new minute starts
    def on_minute_bar(self, event, md, order, service, account, bar):
        #################################################
        # update the entry price if a position is on
        #################################################
        if account:
            if account[self.symbol]:
                if account[self.symbol].position:
                    if self.IsLongPositionOn:
                        self.long_entry_price = account[self.symbol].position.entry_price
                    elif self.IsShortPositionOn:
                        self.short_entry_price = account[self.symbol].position.entry_price

        #
        # don't want to initiate any long positions in the last 5 minutes of the trading day
        # as we won't likely have time to trade out of the position for a profit using 1 minute
        # bar data.
        #
        bar_1 = bar.minute(start=-5, include_empty=True)
        if len(bar_1) >=5:
            if service.system_time < md.market_close_time - service.time_interval(minutes=5, seconds=1):
                #
                # If a position is on we want to check to see if we should take a profit or trade out
                # of a losing position.
                #
                if self.IsLongPositionOn == True:
                    self.checkCloseLong(event, md, order, service, account, bar)
                elif self.IsShortPositionOn == True:
                    self.checkCloseShort(event, md, order, service, account, bar)
                else:  # position isn't on, therefore check to see if we should add a position.
                    if md.L1.timestamp > self.model_start:
                        if bar_1.close[-1] < bar_1.open[-5]:
                            self.IsLongPositionOn = True
                            order_id = order.algo_buy(self.symbol, "market", intent="init", order_quantity=100)
                            self.long_entry_price =  bar_1.close[-1]
                            #self.MyLog(service, service.time_to_string(event.timestamp), "Long", bar_1.open[-5], bar_1.close[-5], bar_1.open[-1], bar_1.close[-1])
                        elif  bar_1.close[-1] > bar_1.open[-5]:
                            self.IsShortPositionOn = True
                            order_id = order.algo_sell(self.symbol, "market", intent="init", order_quantity=100)
                            self.short_entry_price =  bar_1.close[-1]
                            #self.MyLog(service, service.time_to_string(event.timestamp), "Short", bar_1.open[-5], bar_1.close[-5], bar_1.open[-1], bar_1.close[-1])

            else:
                ####################################################################
                # close out of our position at the end of the day because we don't
                # want to carry overnight risk.
                if self.IsLongPositionOn == True:
                    order_id = order.algo_sell(self.symbol, "market", intent="exit")
                    self.IsLongPositionOn = False
                    self.long_entry_price =  0
                    #self.MyLog(service, service.time_to_string(event.timestamp), "EOD-Sell Close", bar_1.open[-5], bar_1.close[-5], bar_1.open[-1], bar_1.close[-1])
                if self.IsShortPositionOn == True:
                    order_id = order.algo_buy(self.symbol, "market", intent="exit")
                    self.IsShortPositionOn = False
                    self.short_entry_price =  0
                    #self.MyLog(service, service.time_to_string(event.timestamp), "EOD-Buy Close", bar_1.open[-5], bar_1.close[-5], bar_1.open[-1], bar_1.close[-1])
    
    ###################################################################
    # Check to see if we should close or reverse a long position
    def checkCloseLong(self, event, md, order, service, account, bar):
        self.HowLongHeld += 1
        bar_1 = bar.minute(start=-5, include_empty=True)
        # there is a position on, therefore we want to check to see if
        # we should realize a profit or stop a loss
        bar_0 = bar.minute()
        if len(bar_0) > 0:
            bv_0 = bar_0.high
            if len(bv_0) > 0:
                if bv_0[0] > self.long_entry_price + self.TargetProfit:
                    # target profit realized, we want to get out of the position.
                    self.IsLongPositionOn = False
                    # send order; use a variable to accept the order_id that order.algo_buy returns
                    order_id = order.algo_sell(self.symbol, "market", intent="exit")
                    self.HowLongHeld = 0
                    #self.MyLog(service, service.time_to_string(event.timestamp), "Sell Profit Close", bar_1.open[-5], bar_1.close[-5], bar_1.open[-1], bar_1.close[-1])
                
                if self.HowLongHeld >= self.MaxMinHeld:  # want to exit position if held for 5 minutes
                    # held for 5 minutes
                    # send order to close the position
                    if bv_0[0] < self.long_entry_price and self.IsShortPositionOn:
                        order_id = order.algo_sell(self.symbol, "market", intent="reverse", order_quantity=100)
                        self.IsLongPositionOn = False
                        self.IsShortPositionOn = True
                        self.long_entry_price = 0.0
                        self.short_entry_price = bar_0.close
                        #self.MyLog(service, service.time_to_string(event.timestamp), "5 Min Sell Close", bar_1.open[-5], bar_1.close[-5], bar_1.open[-1], bar_1.close[-1])
                        self.HowLongHeld = 0

            
    
    ###################################################################
    # Check to see if we should close or reverse a short position
    def checkCloseShort(self, event, md, order, service, account, bar):
        self.HowLongHeld += 1
        bar_1 = bar.minute(start=-5, include_empty=True)
        # there is a position on, therefore we want to check to see if
        # we should realize a profit or stop a loss
        bar_0 = bar.minute()
        if len(bar_0) > 0:
            bv_0 = bar_0.low
            if len(bv_0) > 0:
                if bv_0[0] < self.short_entry_price - self.TargetProfit:
                    # target profit realized, we want to get out of the position.
                    self.IsShortPositionOn = False
                    self.short_entry_price =  0
                    # send order; use a variable to accept the order_id that order.algo_buy returns
                    order_id = order.algo_buy(self.symbol, "market", intent="exit")
                    #self.MyLog(service, service.time_to_string(event.timestamp), "Buy Profit Close", bar_1.open[-5], bar_1.close[-5], bar_1.open[-1], bar_1.close[-1])

                if self.HowLongHeld >= self.MaxMinHeld:  # want to exit position if held for 5 minutes
                    # held for 5 minutes
                    # send order to close the position
                    if bv_0[0] > self.short_entry_price and self.IsShortPositionOn :
                        order_id = order.algo_buy(self.symbol, "market", intent="reverse", order_quantity=100)
                        self.IsShortPositionOn = False
                        self.IsLongPositionOn = True
                        self.short_entry_price =  0.0
                        self.long_entry_price = bar_0.close
                        #self.MyLog(service, service.time_to_string(event.timestamp), "5 Min Buy Close", bar_1.open[-5], bar_1.close[-5], bar_1.open[-1], bar_1.close[-1])
                        self.HowLongHeld = 0
