#!/usr/bin/env python
"""This is the application entrypoint.
Jalapeño and SL-API usage is abstracted in app_lib.
"""
import threading
import logging
import json
import time
from app_lib import SLAPIWrapper
from app_lib import Jalapeno


def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.info("Starting SR-App")
    config = load_config()
    lets_get_thready = threading.Event()
    jalapeno = Jalapeno(**config["jalapeno"])
    sl_api = SLAPIWrapper(config["SL-API"]["netloc"], lets_get_thready)
    try:
        sl_api.vrf_cleanup()
        last_route = None
        while True:
            logging.debug("Polling for optimal path...")
            optimal_path = jalapeno.get_least_utilized_path(
                config["path"]["srcGatewayIP"], config["path"]["dstGatewayIP"]
            )
            # Derive the SL-API route form of what Jalapeño returns.
            optimal_route = {
                "prefix": config["path"]["srcIP"],
                "nexthop_ip": optimal_path[0]["ToInterfaceIP"],
                "nexthop_intf": get_nexthop_intf(optimal_path[0]["ToInterfaceIP"]),
                "label_stack": [int(e["RemotePrefixSID"]) for e in optimal_path[1:]],
            }
            logging.debug(
                "Optimal route: %s -> %s %s",
                optimal_route["prefix"],
                optimal_route["nexthop_ip"],
                str(optimal_route["label_stack"]),
            )
            if optimal_route != last_route:
                logging.info("New optimal route for %s!", optimal_route["prefix"])
                if last_route is not None:
                    logging.debug("Removing previous optimaal route.")
                    sl_api.route_remove(**last_route)
                logging.debug("Adding latest optimal route.")
                sl_api.route_add(**optimal_route)
                last_route = optimal_route
            else:
                logging.debug("Optimal route same as previous, nothing to do.")
            logging.debug("Sleeping for %i seconds.", config["poll_time"])
            time.sleep(config["poll_time"])
    except KeyboardInterrupt:
        logging.warning("Shutting down due to user interrupt!")
    except:
        logging.exception("Unexpected exception!")
    finally:
        # TODO: Ideally move this implicitly into SL-API wrapper
        logging.info("Setting exit flag - will clean up on SL-API heartbeat.")
        lets_get_thready.set()
        sl_api.watchdog_thread.join()


def get_nexthop_intf(nexthop_ip):
    # TODO: Hit device for this or put in Jalapeño
    if nexthop_ip == "172.31.101.44":
        return "HundredGigE0/0/0/0"
    elif nexthop_ip == "172.31.101.48":
        return "Bundle-Ether3"
    elif nexthop_ip == "172.31.101.46":
        return "HundredGigE0/0/0/2"
    else:
        raise Exception("Unknown nexthop!")


def load_config(filename="config.json"):
    config = None
    with open(filename, "r") as config_fd:
        config = json.load(config_fd)
    return config


if __name__ == "__main__":
    main()
