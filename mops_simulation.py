from mops_event import MopsEvent
from mops_event import MopsEventType as MType
from mops_router import MopsRouter
from mops_packet import MopsPacket
from numpy.random import exponential  # argument to this function is 1/lambda
import time
from numpy.random import poisson
from queue import Empty
import math
import matplotlib.pyplot as plt


class MopsSimulation:
    def __init__(self, routers_number, lambd, mi,
                 queue_sizes=None, max_time=None, max_event_count=None, max_packet_count=None, debug=False):
        self.start_sim = time.time()
        self.max_time = max_time
        self.max_event_count = max_event_count
        self.max_packet_count = max_packet_count
        if not 0 < (1/lambd)/(1/mi) < 1:
            raise ValueError("Lambda to mi ratio is not between 0 and 1.")
        self.lambd = 1/lambd  # lambda is Python keyword
        print("Lambda: {}".format(lambd))
        self.mi = 1/mi
        print("Mi: {}".format(mi))
        self.event_count = 0
        self.time = 0
        self.packet_list = []
        self.debug = debug
        if queue_sizes is None:
            self.routers = [MopsRouter() for _ in range(routers_number)]
        else:
            if len(queue_sizes) != routers_number:
                raise ValueError("Number of queues sizes isn't equal to router number.")
            else:
                self.routers = [MopsRouter(queue_sizes[i]) for i in range(routers_number)]
        self.routers_in_queue = []

    def run(self):
        e = MopsEvent(time=self.time, event_type=MType.ARRIVAL, packet_idx=0)  # make first event
        self.packet_list.append(MopsPacket(len(self.packet_list), len(self.routers)))
        self.packet_list[0].times[0][MType.ARRIVAL] = e.time
        self.routers[0].event_queue.put((self.time, e))
        
        while not self.end():
            event, router_idx = self.return_next_event()
            self.handle_event(router_idx, event)

        self.print_statistics()

    def print_handle_event_log(self, event, router_idx):
        """
        Print logs about event occurred.
        :param event: event that has occurred
        :param router_idx: index of a router connected with event
        """

        if event.type == MType.ARRIVAL:
            print("{}. event {}, packet idx {}, router idx {}, at {}"
                  .format(self.event_count, "A", event.packet_idx, router_idx, self.time))
        elif event.type == MType.START_SERVICE:
            print("{}. event {}, packet idx {}, router idx {}, at {}"
                  .format(self.event_count, "S", event.packet_idx,  router_idx, self.time))
        elif event.type == MType.END_SERVICE:
            print("{}. event {}, packet idx {}, router idx {}, at {}"
                  .format(self.event_count, "E", event.packet_idx,  router_idx, self.time))

    def end(self):
        """Return True if simulation should end, return False otherwise."""
        if self.max_time is None and self.max_event_count is None and self.max_packet_count is None:
            return False

        if self.max_time is not None:
            return self.time >= self.max_time
        elif self.max_event_count is not None:
            return self.event_count >= self.max_event_count
        elif self.max_packet_count is not None:
            return len(self.packet_list) >= self.max_packet_count

    def return_next_event(self):
        """Take events from all the event queues and choose this one with the smallest time and return it,
        the other ones add again.
        :return event and router in which event occurs"""
        event_list = []
        for router in self.routers:
            try:
                e = router.event_queue.get(block=False)
                event_list.append(e)
            except Empty:  # if event queue is empty, put None with time=infinity, so it wouldn't be chosen
                event_list.append((math.inf, None))

        event = min(event_list, key=lambda x: x[0])  # return event with the smallest time
        idx = event_list.index(event)
        for i in range(len(event_list)):
            if i != idx:
                self.routers[i].event_queue.put(event_list[i])  # put the others in the queues once again
        return event[1], idx  # return event and router index

    def handle_event(self, router_idx, event):
        """
        Handle event by calling proper function and updating the counters.
        :param router_idx: index of a router in which event has occurred
        :param event: Event to handle
        """
        self.time = event.time
        self.event_count += 1
        if self.debug:
            self.print_handle_event_log(event, router_idx)

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
            self.packet_list[packet_idx].lost = True
        elif not self.routers[router_idx].busy:
            self.put_start_service(router_idx, packet_idx)
        else:
            self.routers[router_idx].add_packet(packet_idx)

        if router_idx == 0:
            self.put_arrival(router_idx, packet_idx)  # add new type.ARRIVAL type event if it is a first router

        self.routers_in_queue.append(self.routers[0].buffer.qsize())

    def put_arrival(self, router_idx, packet_idx):
        """
        Put a MType.ARRIVAL event into router event queue
        :param router_idx: index of a router in which event should be put
        :param packet_idx: index of a packet
        """
        if router_idx == 0:  # if it is the first router we have to make a new packet
            t = self.time + exponential(1/self.lambd)
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

        if self.routers[router_idx].number_of_packets_in_queue() > 0:  # if buffer isn't empty
            packet_idx_temp = self.routers[router_idx].remove_packet()
            self.put_start_service(router_idx, packet_idx_temp)        # put event start new service

        self.routers[router_idx].busy = False  # set router busy to false

        if router_idx != len(self.routers) - 1:  # if this isn't the last router, send packet to the next one
            self.put_arrival(router_idx + 1, packet_idx)

    def put_end_service(self, router_idx, packet_idx):
        """
        Put a MType.END_SERVICE event into router event queue
        :param router_idx: index of a router in which event should be put
        :param packet_idx: index of a packet"""
        t = self.time + exponential(1/self.mi)
        e = MopsEvent(time=t, event_type=MType.END_SERVICE, packet_idx=packet_idx)
        self.packet_list[packet_idx].times[router_idx][MType.END_SERVICE] = t
        self.routers[router_idx].event_queue.put((t, e))

    def print_statistics(self):
        """Print statistics about delays, delays variation and packet losses."""
        plt.plot(self.routers_in_queue)
        plt.show()
        lost = 0
        delays = []
        waiting_in_queue = []
        lost1 = 0
        # packets lost and delays
        for i in range(len(self.routers)):
            print("Number of packet lost in router {}: {}".format(i, self.routers[i].packets_lost))
            lost += self.routers[i].packets_lost
            waiting = []
            service_time = []
            for packet in self.packet_list:
                try:
                    start = packet.times[i][MType.ARRIVAL]
                    end = packet.times[i][MType.START_SERVICE]
                    waiting.append(end - start)
                except KeyError:
                    pass
                try:
                    start = packet.times[i][MType.START_SERVICE]
                    end = packet.times[i][MType.END_SERVICE]
                    service_time.append(end-start)
                except KeyError:
                    pass

            print("Average time of waiting in {} router's queue is: {}".format(i, sum(waiting)/len(waiting)))
            print("Average time of service in {} router's queue is: {}".format(i, sum(service_time) / len(service_time)))
            waiting_in_queue.append(waiting)
        traffic = self.lambd / self.mi
        print("Average traffic (ro) (theoretical): {}".format(traffic))
        print("Average waiting time (theoretical): {}".format(traffic / self.mi / (1 - traffic)))

        for packet in self.packet_list:
            if packet.lost:
                lost1 += 1
            try:
                end = packet.times[len(self.routers) - 1][MType.END_SERVICE]
            except KeyError:
                continue
            else:
                start = packet.times[0][MType.ARRIVAL]
                delays.append(end - start)

        delays.sort()
        if self.debug:
            try:
                print(delays[:50])
            except IndexError:
                print(delays)
        try:
            ipdv99 = delays[math.ceil((len(delays) - 1)*0.99)] - delays[0]  # from swus
            print("IPDV99: {}".format(ipdv99))
            ipdv95 = delays[math.ceil((len(delays) - 1) * 0.95)] - delays[0]
            print("IPDV95: {}".format(ipdv95))
        except IndexError:
            print('No IPDV because all of the packets are lost.')
        if self.debug:
            print(lost)
            print(lost1)

        print("Packet lost: {}%".format(100 * round(lost / len(self.packet_list), 2)))
        print("Packet lost: {}%".format(100 * round(lost1 / len(self.packet_list), 2)))
        print("Number of events: {}, number of packets: {}, time: {}".format(self.event_count, len(self.packet_list), self.time))

        fig, ax = plt.subplots()
        data = ax.hist(delays)

        ax.plot([ipdv95 + delays[0], ipdv95 + delays[0]], [0.95*max(data[0]), 0], color='red')
        ax.text((ipdv95 + delays[0])*0.9, max(data[0]), "centyl 95")
        ax.plot([ipdv99 + delays[0], ipdv99 + delays[0]], [0.9*max(data[0]), 0], color='green')
        ax.text((ipdv99 + delays[0])*0.9, max(data[0]), "centyl99")
        ax.set_xlabel('Delay.')
        ax.set_ylabel('Number of occurrences.')

        print('Simulation took {}s time'.format(time.time() - self.start_sim))
        plt.show()


if __name__ == '__main__':
    s = MopsSimulation(1, 0.5, 0.49, max_packet_count=10000, queue_sizes=[1])
    # s = MopsSimulation(1,1, 2, queue_sizes=[19900])
    s.run()


