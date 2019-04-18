from mops_event import MopsEvent
from mops_event import MopsEventType as MType
from mops_router import MopsRouter
from mops_packet import MopsPacket
from numpy.random import exponential  # argument to this function is 1/lambda
from numpy.random import poisson
from queue import Empty
import math


class MopsSimulation:
    def __init__(self, routers_number, lambd, mi,  queue_sizes=None, max_time=None, max_event_count=None):
        self.max_time = max_time
        self.max_event_count = max_event_count
        self.lambd = lambd  # lambda is Python keyword
        self.mi = mi
        self.event_count = 0
        self.time = 0
        self.packet_list = []
        if queue_sizes is None:
            self.routers = [MopsRouter() for _ in range(routers_number)]
        else:
            if len(queue_sizes) != routers_number:
                raise ValueError("Number of queues sizes isn't equal to router number.")
            else:
                self.routers = [MopsRouter(queue_sizes[i]) for i in range(routers_number)]

    def run(self):
        e = MopsEvent(time=self.time, event_type=MType.ARRIVAL, packet_idx=0)
        self.packet_list.append(MopsPacket(len(self.packet_list), len(self.routers)))
        self.packet_list[0].times[0][MType.ARRIVAL] = e.time
        self.routers[0].event_queue.put((self.time, e))
        
        while not self.end():
            event, router_idx = self.return_next_event()
            self.print_handle_event_log(event[1], router_idx)
            self.handle_event(router_idx, event)
            #print(self.routers[0].data_size)

        self.print_statistics()

    def print_handle_event_log(self, event, router_idx):
        """
        Print logs about event occurred.
        :param event: event that has occurred
        """
        if event.type == MType.ARRIVAL:
            print("{}. event {}, packet idx {}, router idx {}, at {}".format(self.event_count, "A", event.packet_idx, router_idx, self.time))
        elif event.type == MType.START_SERVICE:
            print("{}. event {}, packet idx {}, router idx {}, at {}".format(self.event_count, "S", event.packet_idx,  router_idx, self.time))
        elif event.type == MType.END_SERVICE:
            print("{}. event {}, packet idx {}, router idx {}, at {}".format(self.event_count, "E", event.packet_idx,  router_idx, self.time))

    def end(self):
        """Return True if simulation should end, return False otherwise."""
        if self.max_time is None and self.max_event_count is None:
            return False

        if self.max_time is not None:
            return self.time >= self.max_time
        elif self.max_event_count is not None:
            return self.event_count >= self.max_event_count

    def return_next_event(self):
        event_list = []
        for router in self.routers:
            try:
                e = router.event_queue.get(block=False)
                event_list.append(e)
            except Empty:
                event_list.append((math.inf, None))

        event = min(event_list, key=lambda x: x[0])  # return event with the smallest time
        idx = event_list.index(event)
        for i in range(len(event_list)):
            if i != idx:
                self.routers[i].event_queue.put(event_list[i])
        return event, idx

    def handle_event(self, router_idx, event):
        """
        Handle event by calling proper function and updating the counters.
        :param router_idx: index of a router in which event has occurred 
        """
        self.time, event = event
        self.event_count += 1

        if event.type == MType.ARRIVAL:
            self.handle_type_arrival(router_idx, event.packet_idx)
        elif event.type == MType.START_SERVICE:
            self.handle_type_start_service(router_idx, event.packet_idx)
        elif event.type == MType.END_SERVICE:
            self.handle_type_end_service(router_idx, event.packet_idx)

    def handle_type_arrival(self, router_idx, packet_idx):
        """
        Handle event "packet type.ARRIVAL".
        :param router_idx: index of a router in which event has occurred 
        :param packet_idx: index of a packet
        """
        if self.routers[router_idx].full():
            self.routers[router_idx].packets_lost += 1  # if buffer is full increase lost count
        else:
            if self.routers[router_idx].busy:
                self.routers[router_idx].data_size += 1  # if buffer is busy increase buffer data size
                self.routers[router_idx].add_packet(packet_idx)
            else:
                self.put_start_service(router_idx, packet_idx)  # else add service start event to event queue
        self.put_arrival(router_idx, packet_idx)  # always add new type.ARRIVAL type event

    def put_arrival(self, router_idx, packet_idx):
        """
        Put a MType.ARRIVAL event into router event queue
        :param router_idx: index of a router in which event should be put
        :param packet_idx: index of a packet
        """

        if router_idx == 0:  # if it is the first router we have to make a new packet
            t = self.time + exponential(1 / self.lambd)
            packet = MopsPacket(len(self.packet_list), len(self.routers))
            packet.times[router_idx][MType.ARRIVAL] = t
            self.packet_list.append(packet)
            e = MopsEvent(t, event_type=MType.ARRIVAL, packet_idx=packet.packet_idx)
        else:  # otherwise just send existing packet to the next router
            t = self.packet_list[packet_idx].times[router_idx - 1][MType.END_SERVICE]
            e = MopsEvent(t, event_type=MType.ARRIVAL, packet_idx=packet_idx)
            self.packet_list[packet_idx].times[router_idx][MType.ARRIVAL] = t
        self.routers[router_idx].event_queue.put((t, e))

    def handle_type_start_service(self, router_idx, packet_idx):
        """
        Handle event type.START_SERVICE by putting event type.END_SERVICE and setting router to busy.
        :param router_idx: index of a router in which event should be put
        :param packet_idx: index of a packet
        """
        self.put_end_service(router_idx, packet_idx)
        self.routers[router_idx].busy = True

    def put_start_service(self, router_idx, packet_idx):
        """
        Put a MType.START_SERVICE event into router event queue
        :param router_idx: index of a router in which event should be put
        :param packet_idx: index of a packet
        """
        t = self.time
        e = MopsEvent(time=self.time, event_type=MType.START_SERVICE, packet_idx=packet_idx)
        self.packet_list[packet_idx].times[router_idx][MType.START_SERVICE] = t
        self.routers[router_idx].event_queue.put((t, e))

    def handle_type_end_service(self, router_idx, packet_idx):
        """Handle event MType.END_SERVICE by taking new packet to the service or setting router to not busy
        and by sending packet to the next router if it isn't the last one.
        :param router_idx: index of a router in which event should be put
        :param packet_idx: index of a packet"""
        if self.routers[router_idx].data_size > 0:  # if buffer isn't empty start new service
            packet_idx_temp = self.routers[router_idx].remove_packet()
            self.put_start_service(router_idx, packet_idx_temp)
            self.routers[router_idx].data_size -= 1
        else:
            self.routers[router_idx].busy = False  # otherwise set router busy to false

        if router_idx != len(self.routers) - 1:  # if this isn't the last router, send packet to the next one
            self.put_arrival(router_idx + 1, packet_idx)

    def put_end_service(self, router_idx, packet_idx):
        """
        Put a MType.END_SERVICE event into router event queue
        :param router_idx: index of a router in which event should be put
        :param packet_idx: index of a packet"""
        t = self.time + exponential(1 / self.mi)
        e = MopsEvent(time=t, event_type=MType.END_SERVICE, packet_idx=packet_idx)
        self.packet_list[packet_idx].times[router_idx][MType.END_SERVICE] = t

        self.routers[router_idx].event_queue.put((t, e))

    def print_statistics(self):
        """Print statistics about delays, delays variation and packet losses."""
        lost = 0
        delays = []
        for router in self.routers:
            lost += router.packets_lost
        for packet in self.packet_list:
            try:
                end = packet.times[len(self.routers) - 1][MType.END_SERVICE]
            except KeyError:
                continue
            else:
                start = packet.times[0][MType.ARRIVAL]
                delays.append(end - start)
        delays.sort()
        ipdv99 = delays[math.ceil((len(delays) - 1)*0.99)] - delays[0]  # from swus
        print("IPDV99: {}".format(ipdv99))

        ipdv95 = delays[math.ceil((len(delays) - 1) * 0.95)] - delays[0]
        print("IPDV95: {}".format(ipdv95))

        print("Packet lost: {}%".format(round(100 * lost / len(self.packet_list))))


if __name__ == '__main__':
    s = MopsSimulation(2, 1, 1, max_event_count=10000, queue_sizes=[100, 40])  # czasem ujemne opóźnienie
    #s = MopsSimulation(1, 1, 2, queue_sizes=[19900])

    s.run()
