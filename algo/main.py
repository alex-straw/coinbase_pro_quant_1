import cbpro, time
import pandas as pd
import config

parameters = {'product': 'BTC-USD',
              'level': 2,
              'run_duration': 5,
              'lob_update_interval': 0.5,
              'bid_ask_depth': 5}


def get_relevant_bid_asks(lob, depth):
    """ create a data frame of just the best bids and asks up to a specific depth (parameters)"""
    data = {
            'bid': [item[0] for item in lob['bids'][0:depth]],
            'bid_qty' : [item[1] for item in lob['bids'][0:depth]],
            'ask': [item[0] for item in lob['asks'][0:depth]],
            'ask_qty' : [item[1] for item in lob['asks'][0:depth]]
            }

    bid_ask_df = pd.DataFrame(data=data)
    return bid_ask_df


def get_lob(client, product, level):
    """ using public/auth client, retrieve the order book for a chosen level"""
    lob = client.get_product_order_book(product, level)
    return lob


def main(parameters):
    """ get the authenticated API client, and retrieve LOB for specific market """
    auth_client = cbpro.AuthenticatedClient(config.key, config.b64secret, config.passphrase)

    start_time = time.time()

    while True:
        # Only run for a set duration
        current_time = time.time()
        elapsed_time = current_time - start_time

        # Retrieve lob
        lob = get_lob(auth_client, parameters['product'], parameters['level'])

        bid_ask_df = get_relevant_bid_asks(lob, depth=parameters['bid_ask_depth'])

        print(bid_ask_df)

        # Wait a set duration until requesting lob again
        time.sleep(parameters['lob_update_interval'])

        # Terminate algorithm after chosen duration
        if elapsed_time > parameters['run_duration']:
            print("Algorithm run time: " + str(int(elapsed_time)) + " seconds")
            break


if __name__ == "__main__":
    main(parameters)
