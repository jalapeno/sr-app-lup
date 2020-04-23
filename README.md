# SR-App Sample - Least-Cost Path
This sample SR-App demonstrates how to use Jalapeño to determine the least-cost path through the topology for a provided source IP and use SL-API to instrument that path logic onto the headend router responsible for the traffic. Thus we may traffic engineer the "best" path for highest available bandwidth at all times for the source.

## Usage
```bash
# Assumes pipenv for Python env management
pipenv --three install
# Copy example config
cp config.json.example config.json
# Edit config.json with your details
vi config.json
pipenv run python app.py
```
Note that if there are proxies you may need to set `no_proxy` for your Jalapeño/SL-API instance reachability.

## Implementation
This SR-App requires 4 elements, demonstrated as `config.json`:
* How often to update the path from Jalapeño.
* The source IP, headend router IP, and destination router IP.
* The Jalapeño instance API details.
* The headend router SL-API details.

In its current form, the sample application is written in Python and uses the Jalapeño ArangoDB API and IOS XR SL-API. The ArangoDB API access requires a username and password and access to the `jalapeno` database with `LSNode` and `LS_Topology` collections. The SL-API server is expected to be insecure (no TLS) and without authentication.

To verify the traffic patterns it is recommended to run a single high bandwidth flow from the source to destination, and construct Grafana dashboards visualizing the pathing oscillations of the topology interfaces. Without this SR-App running the flow should create a stable traffic pattern through the network. With this SR-App running the traffic pattern should switch between paths every poll iteration of the Jalapeño API - with no impact to actual performance from the client-server perspective. When the SR-App is stopped traffic should return to a stable traffic pattern as the usual networking protocols hash/make decisions on the flow without any custom traffic engineering.

## Known Issues
* Currently the derivation of the interface name for the SL-API route is static to the demo. Ideally Jalapeño will return the interface name, otherwise we would need to login to the device and determine the associated interface IP's interface name. If you want to run this sample - you will need to edit `app.py`.
* SL-API wrapper `app_lib/sl_api.py` spins up a watchdog thread which needs to be explicitly joined and cleaned up. Ideally this would be done in a class destructor or something along those lines.
* SL-API wrapper watchdog thread exit condition is predicated on SL-API heartbeat or other message. Ideally we do not need to wait for a SL-API message for cleanup.