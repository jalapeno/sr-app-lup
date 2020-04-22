import threading
import logging
from app_lib import SLAPIWrapper

def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.info('Beginning SR-App')
    lets_get_thready = threading.Event()
    sl_api = SLAPIWrapper('10.200.99.50:57400', lets_get_thready)
    try:
        sl_api.vrf_cleanup()
        sl_api.route_add()
        input()
        sl_api.route_remove()
    finally:
        logging.info("Setting exit flag, will clean up soon.")
        lets_get_thready.set()
        sl_api.watchdog_thread.join()

if __name__ == '__main__':
    main()
