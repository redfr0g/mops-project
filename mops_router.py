from queue import PriorityQueue, Queue


class MopsRouter:
    """Router class, each router has event queue and buffer queue."""
    def __init__(self, buffer_size=0):
        self.event_queue = PriorityQueue(0)
        self.buffer_size = buffer_size
        self.packets_lost = 0
        self.data_size = 0
        self.busy = False
        self.buffer = Queue(buffer_size)

    def full(self):
        if self.buffer_size == 0:
            return False
        elif self.buffer_size > self.data_size:
            return False
        else:
            return True

    def add_packet(self, packet_id):
        self.buffer.put(packet_id)

    def remove_packet(self):
        return self.buffer.get()
