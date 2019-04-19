
class MopsPacket:
    def __init__(self, packet_idx, router_number):
        self.packet_idx = packet_idx
        """times is a dictionary that will store:
           key - number of specific router
           value - another dict that will store:
               key - event type
               value - time of specific event
            
            so finally if you want to get time (for example) of packet arrival to second router you should do:
            self.times[2][type.ARRIVAL] 
        """
        self.lost = False
        self.times = {i: dict() for i in range(router_number)}

