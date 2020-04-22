import ipaddress
import os
import sys
import threading
import logging

import grpc

from .proto import sl_global_pb2_grpc
from .proto import sl_global_pb2
from .proto import sl_common_types_pb2
from .proto import sl_version_pb2
from .proto import sl_route_ipv4_pb2_grpc
from .proto import sl_route_ipv4_pb2
from .proto import sl_route_common_pb2


class SLAPIWrapper:
    def __init__(self, netloc, exit_thread_event):
        self.channel = grpc.insecure_channel(netloc)
        self.stub = sl_global_pb2_grpc.SLGlobalStub(self.channel)
        self.exit_event = exit_thread_event
        self.watchdog_thread = self.start_notification_watchdog()

    def start_notification_watchdog(self):
        ready_event = threading.Event()
        watchdog_thread = threading.Thread(
            target=self.__watchdog_main, args=(self.stub, ready_event, self.exit_event)
        )
        watchdog_thread.start()
        ready_event.wait()
        return watchdog_thread

    def __watchdog_main(self, stub, ready_event, exit_event):
        init_msg = sl_global_pb2.SLInitMsg()
        init_msg.MajorVer = sl_version_pb2.SL_MAJOR_VERSION
        init_msg.MinorVer = sl_version_pb2.SL_MINOR_VERSION
        init_msg.SubVer = sl_version_pb2.SL_SUB_VERSION
        timeout = 365 * 24 * 60 * 60
        for response in stub.SLGlobalInitNotif(init_msg, timeout):
            if exit_event.is_set():
                logging.warning("Exit event is set, exiting.")
                break
            if response.EventType == sl_global_pb2.SL_GLOBAL_EVENT_TYPE_VERSION:
                if response.ErrStatus.Status in [
                    sl_common_types_pb2.SLErrorStatus.SL_SUCCESS,
                    sl_common_types_pb2.SLErrorStatus.SL_INIT_STATE_CLEAR,
                    sl_common_types_pb2.SLErrorStatus.SL_INIT_STATE_READY,
                ]:
                    logging.info(
                        "SL-API Server 0x%x, version %d.%d.%d"
                        % (
                            response.ErrStatus.Status,
                            response.InitRspMsg.MajorVer,
                            response.InitRspMsg.MinorVer,
                            response.InitRspMsg.SubVer,
                        )
                    )
                    logging.info("SL-API watchdog started.")
                    ready_event.set()
                else:
                    logging.error(
                        "SL-API watchdog failure: 0x%x", response.ErrStatus.Status
                    )
                    break
            elif response.EventType == sl_global_pb2.SL_GLOBAL_EVENT_TYPE_HEARTBEAT:
                logging.debug("Received SL-API heartbeat.")
            elif response.EventType == sl_global_pb2.SL_GLOBAL_EVENT_TYPE_ERROR:
                if (
                    sl_common_types_pb2.SLErrorStatus.SL_NOTIF_TERM
                    == response.ErrStatus.Status
                ):
                    logging.warning("Received SL-API notice to terminate.")
                    break
                else:
                    logging.error("Error not handled:", response)
            else:
                logging.error(
                    "SL-API initialized with unrecognized response %d",
                    response.EventType,
                )
                break
        self.cleanup()
        exit_event.set()

    def cleanup(self):
        stub = self.__vrf_stub()
        self.__vrf_operation(stub, sl_common_types_pb2.SL_REGOP_UNREGISTER)

    def vrf_cleanup(self):
        stub = self.__vrf_stub()
        self.__vrf_operation(stub, sl_common_types_pb2.SL_REGOP_REGISTER)
        self.__vrf_operation(stub, sl_common_types_pb2.SL_REGOP_EOF)

    def __vrf_stub(self):
        return sl_route_ipv4_pb2_grpc.SLRoutev4OperStub(self.channel)

    def __vrf_operation(
        self,
        stub,
        oper,
        vrf_name="default",
        admin_distance=2,
        purge_interval=500,
        timeout=10,
    ):
        vrfMsg = sl_route_common_pb2.SLVrfRegMsg()
        vrfList = []
        vrfObj = sl_route_common_pb2.SLVrfReg()
        vrfObj.VrfName = vrf_name
        vrfObj.AdminDistance = admin_distance
        vrfObj.VrfPurgeIntervalSeconds = purge_interval
        vrfList.append(vrfObj)
        vrfMsg.VrfRegMsgs.extend(vrfList)
        vrfMsg.Oper = oper
        response = stub.SLRoutev4VrfRegOp(vrfMsg, timeout)

    def route_add(
        self,
        vrf_name="default",
        prefix="172.31.101.67",
        prefix_len=32,
        admin_distance=2,
        nexthop_ip="172.31.101.48",
        nexthop_intf="Bundle-Ether3",
        load_metric=3,
        label_stack=[16005, 16006],
        timeout=10,
    ):
        oper = sl_common_types_pb2.SL_OBJOP_ADD
        stub = self.__route_stub()
        routeList = []
        rtMsg = sl_route_ipv4_pb2.SLRoutev4Msg()
        rtMsg.VrfName = vrf_name
        route = sl_route_ipv4_pb2.SLRoutev4()
        route.Prefix = int(ipaddress.ip_address(prefix))
        route.PrefixLen = prefix_len
        route.RouteCommon.AdminDistance = admin_distance
        paths = []
        path = sl_route_common_pb2.SLRoutePath()
        path.NexthopAddress.V4Address = int(ipaddress.ip_address(nexthop_ip))
        path.NexthopInterface.Name = nexthop_intf
        path.LoadMetric = load_metric
        path.LabelStack.extend(label_stack)
        paths.append(path)
        route.PathList.extend(paths)
        routeList.append(route)
        rtMsg.Routes.extend(routeList)
        rtMsg.Oper = oper
        response = stub.SLRoutev4Op(rtMsg, timeout)
        if (
            sl_common_types_pb2.SLErrorStatus.SL_SUCCESS
            == response.StatusSummary.Status
        ):
            logging.info(
                "Route operation successful: %s",
                str(list(sl_common_types_pb2.SLObjectOp.keys())[oper]),
            )
        else:
            logging.error(
                "Route operation failure 0x%x: %s",
                response.StatusSummary.Status,
                str(list(sl_common_types_pb2.SLObjectOp.keys())[oper]),
            )
            if (
                response.StatusSummary.Status
                == sl_common_types_pb2.SLErrorStatus.SL_SOME_ERR
            ):
                for result in response.Results:
                    logging.debug(
                        "Error code for %s/%d is 0x%x",
                        str(ipaddress.ip_address(result.Prefix)),
                        result.PrefixLen,
                        result.ErrStatus.Status,
                    )

    def route_remove(
        self,
        vrf_name="default",
        prefix="172.31.101.67",
        prefix_len=32,
        admin_distance=2,
        nexthop_ip="172.31.101.48",
        nexthop_intf="Bundle-Ether3",
        load_metric=3,
        label_stack=[16005, 16006],
        timeout=10,
    ):
        oper = sl_common_types_pb2.SL_OBJOP_DELETE
        stub = self.__route_stub()
        routeList = []
        rtMsg = sl_route_ipv4_pb2.SLRoutev4Msg()
        rtMsg.VrfName = vrf_name
        route = sl_route_ipv4_pb2.SLRoutev4()
        route.Prefix = int(ipaddress.ip_address(prefix))
        route.PrefixLen = prefix_len
        route.RouteCommon.AdminDistance = admin_distance
        routeList.append(route)
        rtMsg.Routes.extend(routeList)
        rtMsg.Oper = oper  # Desired ADD, UPDATE, DELETE operation
        response = stub.SLRoutev4Op(rtMsg, timeout)
        if (
            sl_common_types_pb2.SLErrorStatus.SL_SUCCESS
            == response.StatusSummary.Status
        ):
            logging.info(
                "Route operation successful: %s",
                str(list(sl_common_types_pb2.SLObjectOp.keys())[oper]),
            )
        else:
            logging.error(
                "Route operation failure 0x%x: %s",
                response.StatusSummary.Status,
                str(list(sl_common_types_pb2.SLObjectOp.keys())[oper]),
            )
            if (
                response.StatusSummary.Status
                == sl_common_types_pb2.SLErrorStatus.SL_SOME_ERR
            ):
                for result in response.Results:
                    logging.debug(
                        "Error code for %s/%d is 0x%x",
                        str(ipaddress.ip_address(result.Prefix)),
                        result.PrefixLen,
                        result.ErrStatus.Status,
                    )

    def __route_stub(self):
        return sl_route_ipv4_pb2_grpc.SLRoutev4OperStub(self.channel)
