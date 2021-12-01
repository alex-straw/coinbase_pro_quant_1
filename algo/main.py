import cbpro, time
import pandas as pd
import config


parameters = {'product': 'BTC-USD',
              'level': 2}


def get_lob(client, product, level):
    """ using public/auth client, retrieve the order book for a chosen level"""
    lob = client.get_product_order_book(product, level)
    return lob


def main(parameters):
    """ get the authenticated API client, and retrieve LOB for specific market """
    auth_client = cbpro.AuthenticatedClient(config.key, config.b64secret, config.passphrase)
    lob = get_lob(auth_client, parameters['product'], parameters['level'])
    print(lob['bids'])


if __name__ == "__main__":
    main(parameters)

