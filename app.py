#
# Copyright (c) 2016 by cisco Systems, Inc. 
# All rights reserved.

# Standard python libs
import ipaddress
import os
import sys
import threading

# Add the generated python bindings directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

# gRPC generated python bindings
from genpy import sl_global_pb2_grpc
from genpy import sl_global_pb2
from genpy import sl_common_types_pb2
from genpy import sl_version_pb2
from genpy import sl_route_ipv4_pb2_grpc
from genpy import sl_route_ipv4_pb2
from genpy import sl_route_common_pb2

import grpc

# Get the GRPC Server IP address and port number
def get_server_ip_port():
    # Get GRPC Server's IP from the environment
    if 'SERVER_IP' not in os.environ.keys():
        print("Need to set the SERVER_IP env variable e.g.")
        print("export SERVER_IP='10.30.110.214'")
        os._exit(0)

    # Get GRPC Server's Port from the environment
    if 'SERVER_PORT' not in os.environ.keys():
        print("Need to set the SERVER_PORT env variable e.g.")
        print("export SERVER_PORT='57777'")
        os._exit(0)

    return (os.environ['SERVER_IP'], int(os.environ['SERVER_PORT']))

def client_init(stub, event):
    # # Set the client version number based on the current proto files' version
    init_msg = sl_global_pb2.SLInitMsg()
    init_msg.MajorVer = sl_version_pb2.SL_MAJOR_VERSION
    init_msg.MinorVer = sl_version_pb2.SL_MINOR_VERSION
    init_msg.SubVer = sl_version_pb2.SL_SUB_VERSION

    Timeout = 365*24*60*60 # Seconds

    for response in stub.SLGlobalInitNotif(init_msg, Timeout):
        if response.EventType == sl_global_pb2.SL_GLOBAL_EVENT_TYPE_VERSION:
            if (sl_common_types_pb2.SLErrorStatus.SL_SUCCESS ==
                    response.ErrStatus.Status) or \
                (sl_common_types_pb2.SLErrorStatus.SL_INIT_STATE_CLEAR ==
                    response.ErrStatus.Status) or \
                (sl_common_types_pb2.SLErrorStatus.SL_INIT_STATE_READY ==
                    response.ErrStatus.Status):
                print("Server Returned 0x%x, Version %d.%d.%d" %(
                    response.ErrStatus.Status,
                    response.InitRspMsg.MajorVer,
                    response.InitRspMsg.MinorVer,
                    response.InitRspMsg.SubVer))
                print("Successfully Initialized, connection established!")
                # Any thread waiting on this event can proceed
                event.set()
            else:
                print("client init error code 0x%x", response.ErrStatus.Status)
                os._exit(0)
        elif response.EventType == sl_global_pb2.SL_GLOBAL_EVENT_TYPE_HEARTBEAT:
            print("Received HeartBeat")
        elif response.EventType == sl_global_pb2.SL_GLOBAL_EVENT_TYPE_ERROR:
            if (sl_common_types_pb2.SLErrorStatus.SL_NOTIF_TERM ==
                    response.ErrStatus.Status):
                print("Received notice to terminate. Client Takeover?")
                os._exit(0)
            else:
                print("Error not handled:", response)
        else:
            print("client init unrecognized response %d", response.EventType)
            os._exit(0)

def global_thread(stub, event):
    print("Global thread spawned")

    # Initialize the GRPC session. This function should never return
    client_init(stub, event)

    print("global_thread: exiting unexpectedly")
    os._exit(0)

# Spawn a thread for global events
def global_init(channel):
    # Create the gRPC stub.
    stub = sl_global_pb2_grpc.SLGlobalStub(channel)

    # Create a thread sync event. This will be used to order thread execution
    event = threading.Event()

    t = threading.Thread(target = global_thread, args=(stub, event))
    t.start()

    event.wait()

    # Get the globals. Create a SLGlobalsGetMsg
    global_get = sl_global_pb2.SLGlobalsGetMsg()

    # Make an RPC call to get global attributes
    Timeout = 10 # Seconds
    response = stub.SLGlobalsGet(global_get, Timeout)

def vrf_operation(channel, oper):
    # Create the gRPC stub.
    stub = sl_route_ipv4_pb2_grpc.SLRoutev4OperStub(channel)

    vrfMsg = sl_route_common_pb2.SLVrfRegMsg()

    # Create a list to maintain the SLVrfReg objects (in case of batch VRF
    vrfList = []

    # Create an SLVrfReg object and set its attributes
    vrfObj = sl_route_common_pb2.SLVrfReg()
    vrfObj.VrfName = 'default'
    vrfObj.AdminDistance = 2
    vrfObj.VrfPurgeIntervalSeconds = 500

    # Add the registration message to the list
    vrfList.append(vrfObj)

    # Now that the list is completed, assign it to the SLVrfRegMsg
    vrfMsg.VrfRegMsgs.extend(vrfList)

    # Set the Operation
    vrfMsg.Oper = oper
    #
    Timeout = 10 # Seconds
    response = stub.SLRoutev4VrfRegOp(vrfMsg, Timeout)

# A SLRoutev4Msg contains a list of SLRoutev4 (routes)
def route_operation(channel, oper):
    # Create the gRPC stub.
    stub = sl_route_ipv4_pb2_grpc.SLRoutev4OperStub(channel)

    # Create an empty list of routes.
    routeList = []

    # Create the SLRoutev4Msg message holding the SLRoutev4 object list
    rtMsg = sl_route_ipv4_pb2.SLRoutev4Msg()

    # VRF Name
    rtMsg.VrfName = 'default'

    route = sl_route_ipv4_pb2.SLRoutev4()
    # IP Prefix
    route.Prefix = (
        int(ipaddress.ip_address(u'172.31.101.69'))
    )
    # Prefix Length
    route.PrefixLen = 32

    # Administrative distance
    route.RouteCommon.AdminDistance = 2

    # Set the route's paths.
    paths = []

    # Create an SLRoutePath path object.
    path = sl_route_common_pb2.SLRoutePath()

    path.NexthopAddress.V4Address = (
        int(ipaddress.ip_address(u'172.31.101.44'))
    )
    path.NexthopInterface.Name = 'HundredGigE0/0/0/0'
    path.LoadMetric = 24
    path.LabelStack.extend([100004, 100006])
    #path.LabelStack.append(1002)
    paths.append(path)

    # Assign the paths to the route object
    if oper != sl_common_types_pb2.SL_OBJOP_DELETE:
        route.PathList.extend(paths)

    # Append the route to the route list (bulk routes)
    routeList.append(route)
    
    # Done building the routeList, assign it to the route message.
    rtMsg.Routes.extend(routeList)

    # Make an RPC call
    Timeout = 10 # Seconds
    rtMsg.Oper = oper # Desired ADD, UPDATE, DELETE operation
    response = stub.SLRoutev4Op(rtMsg, Timeout)

    # Check the received result from the Server 
    if (sl_common_types_pb2.SLErrorStatus.SL_SUCCESS == 
            response.StatusSummary.Status):
        print("Route %s Success!" %(
            list(sl_common_types_pb2.SLObjectOp.keys())[oper]))
    else:
        print("Error code for route %s is 0x%x" % (
            list(sl_common_types_pb2.SLObjectOp.keys())[oper],
            response.StatusSummary.Status
        ))
        # If we have partial failures within the batch, let's print them
        if (response.StatusSummary.Status == 
            sl_common_types_pb2.SLErrorStatus.SL_SOME_ERR):
            for result in response.Results:
                print("Error code for %s/%d is 0x%x" %(
                    str(ipaddress.ip_address(result.Prefix)),
                    result.PrefixLen,
                    result.ErrStatus.Status
                ))
        os._exit(0)

# Setup the GRPC channel with the server, and issue RPCs
if __name__ == '__main__':
    server_ip, server_port = get_server_ip_port()

    print("Using GRPC Server IP(%s) Port(%s)" %(server_ip, server_port))

    # Create the channel for gRPC.
    channel = grpc.insecure_channel(str(server_ip) + ":" + str(server_port))

    # Spawn a background thread to Initialize the client and listen on notifications
    global_init(channel)

    # Send an RPC for VRF registrations
    vrf_operation(channel, sl_common_types_pb2.SL_REGOP_REGISTER)

    # RPC EOF to cleanup any previous stale routes
    vrf_operation(channel, sl_common_types_pb2.SL_REGOP_EOF)

    # RPC route operations
    route_operation(channel, sl_common_types_pb2.SL_OBJOP_ADD)

    os._exit(0)
