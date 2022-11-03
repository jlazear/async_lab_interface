from typing import Optional, Callable
import asyncio
import json
from collections import deque, defaultdict
from pyvisa import ResourceManager, InvalidSession

from interface import *
import aio_queues

#TODO read from file, or parse from interface.py
instr_dict = {'VNA': VectorNetworkAnalyzer,
              'PowerSupply': PowerSupply}

class Controller:
    def __init__(self, rm: str=None, queue=None, responses=None, cntrl_id:str=None):
        self.queue = deque()
        receive_coro = aio_queues.bind_receive_queue(self, self.queue)  #TODO parameterize
        self.outbox = deque()
        send_coro = aio_queues.bind_send_queue(self, self.outbox, exchange_name='e_responses')
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

        # tasks (coroutines) to be run
        self._coroutines = [self.enqueue_interface_async(), self.enqueue_station_async(), receive_coro, send_coro]
        self._tasks = []

    @staticmethod
    def format_idn(idn: str) -> None:
        return idn.strip().split('-')

    def create_interface(self, resource_name: str, station_name: str) -> AsynchronousInterface:
        """@expose Add a new instrument to the controller, at the specified `resource_name` and `station_name`"""
        with self.resource_manager.open_resource(resource_name, timeout=5) as instr:
            #TODO add error handling for invalid resource_names
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
        self.create_task(new_interface.process_commands_forever())
        return new_interface

    async def enqueue_station_async(self) -> None:
        """Asynchronous wrapper around `enqueue_station`"""
        while not self._stop:
            self.enqueue_station()
            await asyncio.sleep(0.01)

    def enqueue_station(self) -> None:
        """Read from the command queue and put them into the appropriate station queue."""
        #TODO change to RabbitMQ consume and add deserializer
        # while not self._stop:  #TODO #FIXME
        if self.queue:
            msg = json.loads(self.queue.popleft())
            if msg['id'] == 'controller':
                print("CONTROLLER TYPE")  #DELME
                print(f"{msg = }")  #DELME
                try:
                    method = getattr(self, msg['cmd'])
                    method(*msg['args'], **msg['kwargs'])
                except AttributeError:
                    self.outbox.append(f"Invalid command {msg}")
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

    async def enqueue_interface_async(self) -> None:
        """Asynchronous wrapper around `enqueue_interface`"""
        while not self._stop:
            self.enqueue_interface()
            await asyncio.sleep(0.01)

    # def enqueue_interface(self) -> None:
    #     """Iterate through the station queues and move them to the corresponding interface queues."""
    #     # while not self._stop:  #TODO #FIXME
    #     if self.station_queue_not_empty():
    #         for station, value in self.station_queues.items():
    #             print(f"enqueueing {station}")  #DELME
    #             for iid, (cmd, callback, args, kwargs) in value:
    #                 #TODO add error handling for invalid instruments
    #                 print(f"-->enqueueing {iid} {(cmd, callback, args, kwargs)}")  #DELME
    #                 interface = self.instruments[iid]['interface']
    #                 interface.add_to_inbox(cmd, *args, callback=callback, **kwargs)

    def enqueue_interface(self) -> None:
        """Iterate through the station queues and move them to the corresponding interface queues."""
        # while not self._stop:  #TODO #FIXME
        if self.station_queue_not_empty():
            for station, value in self.station_queues.items():
                print(f"enqueueing {station}")  #DELME
                while value:
                    iid, (cmd, callback, args, kwargs) = value.popleft()
                    print(f"-->enqueueing {iid} {(cmd, callback, args, kwargs)}")  #DELME
                    interface = self.instruments[iid]['interface']
                    interface.add_to_inbox(cmd, *args, callback=callback, **kwargs)

    # def add_to_responses(self) -> None:
    #     """Move outbox to responses message queue."""
    #     #TODO convert to RabbitMQ
    #     # while not self._stop:  #TODO #FIXME
    #     if self.outbox:
    #         msg = self.outbox.popleft()
    #         self.responses.append(json.dumps(msg))

    def create_task(self, coro):
        """Create a new asynchronous task and register it with the event loop"""
        loop = asyncio.get_event_loop()
        task = loop.create_task(coro)
        self._tasks.append(task)

    async def run_async(self):
        loop = asyncio.get_event_loop()
        for coro in self._coroutines:
            task = loop.create_task(coro)
            self._tasks.append(task)

        while not self._stop:
            await asyncio.sleep(1)
        
        for task in self._tasks:
            try:
                task.cancel()
            except:
                pass
        loop.close()
        
    def run(self):
        try:
            loop = asyncio.get_running_loop()
            self._tasks.append(loop.create_task(self.run_async()))
        except RuntimeError:
            print("No existing event loop found, creating a new one!")
            asyncio.run(self.run_async())

    #TODO add controller housekeeping functions
    def list_instruments(self) -> None:
        """@expose List the instruments controlled by this controller"""
        toret = {}
        for iid, d in self.instruments.items():
            toret[iid] = (d['station'], d['resource_name'])
        self.outbox.append(toret)

    def list_methods(self) -> None:
        """@expose List the methods provided by this controller"""
        d = {}
        methods = inspect.getmembers(self, predicate=inspect.ismethod)
        for name, method in methods:
            signature = inspect.signature(method)
            doc = method.__doc__
            if doc and doc.startswith("@expose"):
                d[name] = {}
                d[name]['signature'] = f"{name}({signature})"
                d[name]['docstring'] = doc[len('@expose '):]
        self.outbox.append(d)


if __name__ == "__main__":
    controller = Controller(rm='default.yaml@sim')
    controller.run()