import cbpro, time
import pandas as pd
import config

parameters = {'product': 'BTC-USD',
              'level': 2,
              'run_duration': 5,
              'lob_update_time': 0.5}


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

        # Wait a set duration until requesting lob again
        time.sleep(parameters['lob_update_time'])

        # Terminate algorithm after chosen duration
        if elapsed_time > parameters['run_duration']:
            print("Algorithm run time: " + str(int(elapsed_time)) + " seconds")
            break


if __name__ == "__main__":
    main(parameters)
