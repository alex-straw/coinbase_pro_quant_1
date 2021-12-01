import cbpro, time
import pandas as pd
import config
import numpy as np

parameters = {'product': 'DOGE-GBP',
              'level': 2,
              'run_duration': 180,
              'lob_update_interval': 0.25,
              'bid_ask_depth': 50}


# Gradient trader
# Observes the order book
# Waits until it can see sufficient pressure on either side of the limit order book (currently just spot buy).
# If buy pressure is increasing, as determined by the gradient of the first x (depth) orders.
# Purchase n of the cryptocurrency at the best ask
# Limit sell @ buy price + 2% (CBPRO has a 0.5% maker taker fee each way)
# Stop loss @ buy price - 1%

def get_bid_asks(lob, lob_depth):
    """ create a data frame of just the best bids and asks up to a specific depth (parameters)"""
    # List comprehensions are used to extract bid and ask data - this is relatively efficient
    # Note that each list must be converted to numeric, as default is str
    data = {
        'bid': pd.to_numeric([item[0] for item in lob['bids'][0:lob_depth]]),
        'bid_qty': pd.to_numeric([item[1] for item in lob['bids'][0:lob_depth]]),
        'ask': pd.to_numeric([item[0] for item in lob['asks'][0:lob_depth]]),
        'ask_qty': pd.to_numeric([item[1] for item in lob['asks'][0:lob_depth]])
    }

    bid_ask_df = pd.DataFrame(data=data)

    # Create an additional two columns displaying the cumulative sum of bids and asks to the required depth
    bid_ask_df['cumsum_bid'] = bid_ask_df['bid_qty'].cumsum()
    bid_ask_df['cumsum_ask'] = bid_ask_df['ask_qty'].cumsum()

    return bid_ask_df


class GradientTrader:

    def __init__(self, memory_size, lob_depth):
        # memory_size:  how many data points will the trader remember
        # lob_depth: how many orders will the trader look past the best ask & bid price (in the limit order book)
        # paper_hands_ratio: how long will the trader hold on the spot buy
        self.memory_size = memory_size
        self.lob_depth = lob_depth
        self.cur_bid_ask_df = pd.DataFrame()
        self.memory_arr = []
        self.trade_history = []
        self.capital = 1000
        self.market_pressure_ratio = np.NaN
        self.market_pressure_arr = []
        self.average_pressure_ratio = np.NaN

        # Market pressure ratio threshold for entering long position
        # Initially this value is constant
        self.trade_threshold = 1.3
        self.trade_size = 500  # how large the trade will be in USD
        self.position_hold_time = 30  # How long the trade will be open in seconds

        # If a trade takes place, update these
        self.trade_active = False
        self.long_price = np.NaN
        self.long_qty = np.NaN
        self.trade_entry_time = np.NaN

    def update_memory(self, lob, current_time):
        # Update the bid_ask_df attribute for GradientTrader
        self.cur_bid_ask_df = get_bid_asks(lob, self.lob_depth)
        # Memory array : Timestamp | bid_gradient | ask_gradient | spread
        self.memory_arr.extend([evaluate_market_state(current_time, self.cur_bid_ask_df)])
        # Keep memory array at a consistent length according to instance of GradientTrader
        if len(self.memory_arr)-1 > self.memory_size:
            self.memory_arr.pop(0)

        self.compute_trade_decision()

    def calculate_average_market_pressure(self):
        # calculate weighted avg - skewed towards recent values
        self.average_pressure_ratio = sum(self.market_pressure_arr)/self.memory_size

    def calculate_recent_market_pressure(self):
        """ simply looks at the most recent market pressure in last LOB call """
        self.market_pressure_ratio = abs(self.memory_arr[-1][2] / self.memory_arr[-1][4])
        self.market_pressure_arr.append(self.market_pressure_ratio)
        if len(self.market_pressure_arr) > self.memory_size:
            self.market_pressure_arr.pop(0)

    def compute_trade_decision(self):
        """
        For the gradient trader, the market_pressure_ratio represents the bid side gradient (aka buy side pressure)
        divided by the ask side gradient (aka sell side pressure).
        This algorithm will test whether a high ratio represents a good time to place a spot buy order.
        Currently, this only looks at the exact pressure ratio for the given timestamp.
        This will eventually take into account the changes in this ratio included in the trader's memory.
        """

        self.calculate_recent_market_pressure()

        if len(self.market_pressure_arr) == self.memory_size:  # Check enough data has been collected
            self.calculate_average_market_pressure()  # Calculate weighted market pressure
            if self.average_pressure_ratio > self.trade_threshold:  # Check market pressure is above threshold to trade
                if not self.trade_active:  # Only open a trade if there is not currently one active
                    print("Entering a long position, market pressure ratio: " + str(self.average_pressure_ratio) + ".")
                    self.enter_long_position(time.time())

    def enter_long_position(self, cur_time):
        """
        For now, ignore market impact and available quantity. Enter a $500 position long at the best ask.
        """
        self.long_price = self.memory_arr[-1][3]
        self.long_qty = self.trade_size / self.long_price
        self.trade_entry_time = cur_time
        self.trade_active = True
        self.capital -= self.trade_size

    def exit_long_position(self, cur_time):
        """
        Sell the position to the best bid if the trade has been open for longer than the specified duration
        """
        if cur_time - self.trade_entry_time > self.position_hold_time:
            # Change in price, multiplied by the amount of the token purchased
            # Update total capital owned
            self.capital += self.memory_arr[-1][1] * self.long_qty
            self.long_price = np.NaN
            self.long_qty = np.NaN
            self.trade_entry_time = np.NaN
            self.trade_active = False
            print(self.capital)


def calculate_gradient(best_price, worst_price, cumsum_qty):
    """
    Gradient = dy/dx = d(qty)/d(price)
    This function approximates the LOB bid/ask gradients to be straight lines of the form: y = mx + c
    """
    # As demand is on the left, i.e best price > worst price, its gradient should be positive
    # As supply is on the right, i.e best price < worst price, its gradient should be negative
    return (best_price - worst_price) / cumsum_qty


def evaluate_market_state(time, bid_ask_df):
    """
    For each API call, evaluate the ask and bid LOB gradients.
    :returns a list consisting of:
        -api call time
        -bid gradient
        -ask gradient
        -spread (difference between best ask and the best bid)
    """

    bid_gradient = calculate_gradient(best_price=bid_ask_df['bid'].iloc[0],
                                      worst_price=bid_ask_df['bid'].iloc[-1],
                                      cumsum_qty=bid_ask_df['cumsum_bid'].iloc[-1])

    ask_gradient = calculate_gradient(best_price=bid_ask_df['ask'].iloc[0],
                                      worst_price=bid_ask_df['ask'].iloc[-1],
                                      cumsum_qty=bid_ask_df['cumsum_ask'].iloc[-1])

    spread = bid_ask_df['ask'].iloc[0] - bid_ask_df['bid'].iloc[0]

    best_bid = bid_ask_df['bid'].iloc[0]
    best_ask = bid_ask_df['ask'].iloc[0]

    return [time,
            best_bid,
            bid_gradient,
            best_ask,
            ask_gradient,
            spread]


def get_lob(client, product, level):
    """ using public/auth client, retrieve the order book for a chosen level"""
    lob = client.get_product_order_book(product, level)
    return lob


def main(parameters):
    """ get the authenticated API client, and retrieve LOB for specific market """
    auth_client = cbpro.AuthenticatedClient(config.key, config.b64secret, config.passphrase)

    start_time = time.time()

    memory_arr = []

    trader_zero = GradientTrader(memory_size=10,
                                 lob_depth=10)

    while True:
        # Only run for a set duration
        current_time = time.time()
        elapsed_time = current_time - start_time

        # Retrieve lob - standard for all algorithms tested here
        lob = get_lob(auth_client, parameters['product'], parameters['level'])

        trader_zero.update_memory(lob, current_time)

        # Checks if the trader should exit the trade
        trader_zero.exit_long_position(current_time)

        print(trader_zero.average_pressure_ratio)

        # Wait a set duration until requesting lob again
        time.sleep(parameters['lob_update_interval'])

        # Terminate algorithm after chosen duration
        if elapsed_time > parameters['run_duration']:
            print("Algorithm run time: " + str(int(elapsed_time)) + " seconds")
            break


if __name__ == "__main__":
    main(parameters)
