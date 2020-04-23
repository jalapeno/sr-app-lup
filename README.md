# SR-App Sample - Least-Cost Path
This sample SR-App demonstrates how to use Jalapeño to determine the least-cost path through the topology for a provided source IP and use SL-API to instrument that path logic onto the headend router responsible for the traffic. Thus we may traffic engineer the "best" path for highest available bandwidth at all times for the source.

This requires 4 elements, demonstrated as `config.json`:
* How often to update the path from Jalapeño.
* The source IP, headend router IP, and destination router IP.
* The Jalapeño instance API details.
* The headend router SL-API details.

In its current form, the sample application is written in Python and uses the Jalapeño ArangoDB API and IOS XR SL-API. The ArangoDB API access requires a username and password and access to the `jalapeno` database with `LSNode` and `LS_Topology` collections. The SL-API server is expected to be insecure (no TLS) and without authentication.

To verify the traffic patterns it is recommended to run a single high bandwidth flow from the source to destination, and construct Grafana dashboards visualizing the pathing oscillations of the topology interfaces. Without this SR-App running the flow should create a stable traffic pattern through the network. With this SR-App running the traffic pattern should switch between paths every poll iteration of the Jalapeño API - with no impact to actual performance from the client-server perspective. When the SR-App is stopped traffic should return to a stable traffic pattern as the usual networking protocols hash/make decisions on the flow without any custom traffic engineering.

