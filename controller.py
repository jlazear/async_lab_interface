from typing import Optional, Callable
import asyncio
import json
from collections import deque, defaultdict
from pyvisa import ResourceManager, InvalidSession

from interface import *

#TODO read from file, or parse from interface.py
instr_dict = {'VNA': VectorNetworkAnalyzer,
              'PowerSupply': PowerSupply}

class Controller:
    def __init__(self, rm: str=None, queue=None, responses=None, cntrl_id:str=None):
        self.queue = queue or deque()
        self.responses = responses or deque()
        self.outbox = deque()
        self.id = cntrl_id or 'controller'

        # stations = {'stationname1': {'rn0': interface0, 'rn1': interface1, ...},
        #             'stationname2': {'rnN': interfaceN, 'rnNp1': interfaceNp1, ...}, ...}
        # instruments = {'rn0': {'interface': interface0, 'station': 'stationname1'},
        #                'rn1': {'interface': interface1, 'station': 'stationname1'}, ...}
        self.stations = defaultdict(dict)
        self.instruments = defaultdict(dict)
        self.station_queues = defaultdict(deque)

        self.resource_manager = ResourceManager(rm if rm else 'default.yaml@sim')

        # control flags
        self._stop = False

    @staticmethod
    def format_idn(idn: str) -> None:
        return idn.strip().split('-')

    def create_interface(self, resource_name: str, station_name: str) -> AsynchronousInterface:
        with self.resource_manager.open_resource(resource_name, timeout=5) as instr:
            #TODO add error handlign for invalid resource_names
            ret = instr.query("*IDN?")
        
        instr_type, inst_id = self.format_idn(ret)
        new_interface = instr_dict[instr_type](resource_name=resource_name, rm=self.resource_manager,
                                               outbox=self.outbox, inst_id=inst_id)
        self.stations[station_name][inst_id] = new_interface
        self.instruments[inst_id]['interface'] = new_interface
        self.instruments[inst_id]['station'] = station_name
        self.instruments[inst_id]['resource_name'] = resource_name
        self.station_queues[station_name]  # touch station_name; creates if doesn't exist, otherwise nothing
        self.outbox.append(f"{self.id} / create_interface: {instr_type} ({inst_id}) [{station_name}] @ {resource_name}")
        return new_interface

    # async def enqueue_station(self):
    def enqueue_station(self) -> None:
        """Read from the command queue and put them into the appropriate station queue."""
        #TODO change to RabbitMQ consume and add deserializer
        # while not self._stop:  #TODO #FIXME
        if self.queue:
            msg = json.loads(self.queue.popleft())
            if msg['id'] == 'controller':
                print("CONTROLLER TYPE")  #DELME
                print(f"{msg = }")  #DELME
                method = getattr(self, msg['cmd'])
                method(*msg['args'], **msg['kwargs'])
            else:
                print("INSTRUMENT TYPE")  #DELME
                print(f"{msg = }")  #DELME
                iid = msg['id']
                try:
                    station = self.instruments[iid]['station']
                    newmsg = (msg['cmd'], None, msg['args'], msg['kwargs'])
                    self.station_queues[station].append((iid, newmsg))
                except KeyError:
                    pass  # ignore messages for instruments we do not own

    def station_queue_not_empty(self) -> bool:
        """Checks if the station queue has no commands to queue up."""
        if not self.station_queues:
            return False
        for value in self.station_queues.values():
            if value:
                return True
        return False

    def enqueue_interface(self) -> None:
        """Iterate through the station queues and move them to the corresponding interface queues."""
        # while not self._stop:  #TODO #FIXME
        if self.station_queue_not_empty():
            for station, value in self.station_queues.items():
                print(f"enqueueing {station}")  #DELME
                for iid, (cmd, callback, args, kwargs) in value:
                    #TODO add error handling for invalid instruments
                    print(f"-->enqueueing {iid} {(cmd, callback, args, kwargs)}")  #DELME
                    interface = self.instruments[iid]['interface']
                    interface.add_to_inbox(cmd, *args, callback=callback, **kwargs)

    def add_to_responses(self) -> None:
        """Move outbox to responses message queue."""
        #TODO convert to RabbitMQ
        # while not self._stop:  #TODO #FIXME
        if self.outbox:
            msg = self.outbox.popleft()
            self.responses.append(json.dumps(msg))

    #TODO add controller housekeeping functions
    #TODO make message queue
