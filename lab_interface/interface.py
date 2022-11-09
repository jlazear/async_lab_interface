from typing import Optional, Callable
import inspect
import asyncio
from collections import deque, defaultdict
from pyvisa import ResourceManager, InvalidSession
# import numpy as np


class AsynchronousInterface:
    def __init__(self, resource_name: str, rm: ResourceManager, 
                 inst_id: Optional[str]=None,
                 inst_type: Optional[str]=None,
                 visa_timeout:int=10, read_term:str='\n',
                 write_term:str='\r\n',
                 aiosleep:float=0.01, timeout:int=300,
                 outbox:Optional[deque]=None,
                 interactive:bool=False) -> None:
        #TODO add error checking
        self.resource_name = resource_name         # name of VISA resource
        self.resource_manager = rm                 # VISA resource manager
        self.id = inst_id or id(self)              # instrument ID
        self.inst_type = inst_type or 'Generic'    # Instrument type
        self.visa_timeout = visa_timeout           # low-level VISA timeout (in ms)
        self.timeout = timeout                     # timeout for interface actions
        self.read_term = read_term                 # read message termination characters
        self.write_term = write_term               # write message termination characters
        self.aiosleep = aiosleep                   # internal asyncio loop sleep period
        self.interactive = interactive             # True = stand-alone mode, no pre-existing event loop

        # VISA connection to instrument
        self._conn = None
        self.connect()

        # command and output FIFOs
        self.inbox = deque()
        self.outbox = deque() if (outbox is None) else outbox
        
        # control flag
        self._stop = True
        self._task = None
        self._busy = False

    def connect(self) -> None:
        """
        Connects to target resource if not connected. Safe to call when resource is already open."""
        try:
            self._conn.session
        except (InvalidSession, AttributeError):
            self._conn = self.resource_manager.open_resource(self.resource_name, timeout=self.visa_timeout,
                                                             read_termination=self.read_term,
                                                             write_termination=self.write_term)

    @staticmethod
    def passfunc(r: bytes) -> None:
        pass
    
    # def to_outbox(self, value: bytes, source: Optional[str]=None) -> None:
    #     self.outbox.append(f"{self.id} / {source}}: {value}")

    def busy(self) -> bool:
        """Returns True if inbox is empty and not processing a command."""
        return (self.inbox or self._busy)

    async def read_async(self, *args, **kwargs) -> str:
        """Asynchronous read of resource until `term_char` encountered. Will not timeout."""
        self.connect()
        toret = []
        c = None
        while c != self.read_term[-1].encode():
            await asyncio.sleep(self.aiosleep)
            c = self._conn.read_bytes(1)
            if c:
                toret.append(c)
        r = b''.join(toret)
        return r

    async def write_async(self, msg: str, *args, **kwargs) -> None:
        """Write to resource. Is blocking because write assumed to be very fast."""
        self._conn.write(msg)

    async def slow_async(self, t: int=5, *args, **kwargs) -> None:  #DELME
        """A slow-running task for testing."""
        print("entered slow")
        for i in range(t):
            print(f"-->slow {i}")
            await asyncio.sleep(1)
        print("exiting slow")

    async def sleep_async(self, period: float=5, *args, **kwargs) -> None:
        """Sleep this instrument for `period` seconds."""
        self._busy = True
        await asyncio.sleep(period)
        self._busy = False

    def add_to_inbox(self, cmd: str, *args, callback: Optional[Callable[..., None]]=None, **kwargs) -> None:
        """Schedules command for execution. First pos arg is cmd, rest are args/kwargs."""
        self.inbox.append((cmd, callback, args, kwargs))
    
    async def process_command(self) -> None:
        """Process a single command off the queue."""
        if not self.inbox:
            return

        self._busy = True
        cmd, callback, args, kwargs = self.inbox.popleft()
        method = getattr(self, cmd)
        if asyncio.iscoroutinefunction(method):
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(method(*args, **kwargs))
            try:
                ret = await asyncio.wait_for(self._task, timeout=self.timeout)  # give up after timeout
                if callback:
                    callback(ret)
            except TimeoutError:
                print(f"task {self._task} timed out")  #DELME
                #TODO handle timeouts meaningfully
        else:
            try:
                method(*args, **kwargs)
            except (AttributeError, TypeError) as e:
                print(f"Invalid command: {self.id} {cmd} {args} {kwargs}")
                self.outbox.append(f"Invalid command: {self.id} {cmd} {args} {kwargs}")
        self._busy = False

    async def process_all_commands(self) -> None:
        """Process all of the commands in the queue."""
        while self.inbox:
            await self.process_command()

    async def process_commands_forever(self) -> None:
        """Continually processes commands in the queue until stopped by self.stop()."""
        self._stop = False
        while not self._stop:
            if not self.inbox:
                await asyncio.sleep(self.aiosleep)  #FIXME
                continue
            await self.process_command()

    def stop(self) -> None:
        """Stops self.process_commands_forever loop."""
        self._stop = True
        self._task.cancel()

    # Base functions
    def ask(self, cmd: str, callback: Optional[Callable[..., None]]=None) -> None:
        """@expose Ask (write then read response) of command `cmd`"""
        if callback is None:
            callback = lambda r: self.outbox.append(f"{self.id} / ask: {r}")
        self.add_to_inbox("write_async", cmd, callback=False)
        self.add_to_inbox("read_async", callback=callback)
        
        if self.interactive:
            asyncio.run(interface.process_all_commands())


    def read(self, callback: Optional[Callable[..., None]]=None) -> None:
        """@expose Read instrument buffer until termination character encountered"""
        if callback is False:
            callback = self.passfunc
        elif not callback:
            callback = lambda r: self.outbox.append(f"{self.id} / read: {r}")

        self.add_to_inbox("read_async", callback=callback)

        if self.interactive:
            asyncio.run(interface.process_all_commands())


    def write(self, msg: str, callback: Optional[Callable[..., None]]=None) -> None:
        """@expose Write the command `cmd` to the instrument"""
        if callback is False:
            callback = self.passfunc
        elif not callback:
            callback = lambda x: self.outbox.append(f"{self.id} / write: {msg}")

        print(f"--> instr.write {msg = }")  #DELME
        self.add_to_inbox("write_async", msg, callback=callback)

        if self.interactive:
            asyncio.run(interface.process_all_commands())

    def sleep(self, period: float, callback: Optional[Callable[..., None]]=None) -> None:
        """@expose Prevent commands from being sent to instrument for `period` seconds."""
        if callback is False:
            callback = self.passfunc
        elif not callback:
            callback = lambda x: self.outbox.append(f"{self.id} / sleep: {period} s")
        print(f"IN sleep {period = }")  #DELME
        self.add_to_inbox("sleep_async", period, callback=callback)

        if self.interactive:
            asyncio.run(interface.process_all_commands())        

    # default SCPI commands
    def idn(self) -> None:
        """@expose Get the ID of the instrument. Asks the *IDN? command."""
        callback = lambda r: self.outbox.append(f"{self.id} / idn: {r.strip().decode()}")
        self.ask("*IDN?", callback=callback)

    #TODO add other default commands...

    def list_methods(self) -> None:
        d = {}
        methods = inspect.getmembers(self, predicate=inspect.ismethod)
        for name, method in methods:
            signature = inspect.signature(method)
            doc = method.__doc__
            if doc and doc.startswith("@expose"):
                d[name] = {}
                d[name]['signature'] = f"{name}{signature}"
                d[name]['docstring'] = doc[len('@expose '):]
        self.outbox.append(d)


class PowerSupply(AsynchronousInterface):
    """@expose This is a power supply."""
    def __init__(self, resource_name: str, rm: ResourceManager, inst_type: str='PowerSupply', *args, **kwargs) -> None:
        super().__init__(resource_name, rm, inst_type=inst_type, *args, **kwargs)

    def set_voltage(self, Vdc: float) -> None:
        """@expose Set the voltage in V"""
        callback = lambda r: self.outbox.append(f"{self.id} ({self.inst_type}) / set_voltage: {Vdc} V")
        s = f"VOLT {Vdc:.2f}"
        self.write(s, callback=callback)

    def get_voltage(self) -> None:
        """@expose Get the voltage in V"""
        callback = lambda r: self.outbox.append(f"{self.id} ({self.inst_type}) / get_voltage: {r} V")
        self.ask("VOLT?", callback=callback)

    def set_output(self, enable: bool=True) -> None:
        """@expose Enable (if `enable`=True) or disable (if `enable`=False) the output."""
        callback = lambda r: self.outbox.append(f"{self.id} ({self.inst_type}) / set_output: {'1' if enable else '0'}")
        self.write(f"OUTPUT {1 if enable else 0}", callback=callback)

    def get_output(self, enable: bool=True) -> None:
        """@expose Get the current output state"""
        callback = lambda r: self.outbox.append(f"{self.id} ({self.inst_type}) / get_output: {'1' if r else '0'}")
        self.write(f"OUTPUT?", callback=callback)

class VectorNetworkAnalyzer(AsynchronousInterface):
    """@expose This is a VNA."""
    def __init__(self, resource_name: str, rm: ResourceManager, inst_type: str='VNA', *args, **kwargs) -> None:
        super().__init__(resource_name, rm, inst_type=inst_type, *args, **kwargs)

    def set_frequency_range(self, start:float, end:float, Npoints:int) -> None:
        """@expose Sets the frequency range from `start` to `end` in GHz, with `Npoints` steps."""
        callback = lambda r: self.outbox.append(f"{self.id} ({self.inst_type}) / set_frequency_range: {start:.2f} -> {end:.2f} ({Npoints})")
        self.write(f"SENSE:FREQUENCY:START {start:.2f}", callback=False)
        self.write(f"SENSE:FREQUENCY:STOP {end:.2f}", callback=False)
        self.write(f"SENSE:FREQUENCY:POINTS {Npoints}", callback=callback)

    def get_frequency_range(self) -> None:
        """@expose Get the current frequency range: start(GHz)/end(GHz)/Npoints(unitless)"""
        callback = lambda r: self.outbox.append(f"{self.id} ({self.inst_type}) / get_freq_start: {float(r):.2f}")
        self.ask(f"SENSE:FREQUENCY:START?", callback=callback)
        callback = lambda r: self.outbox.append(f"{self.id} ({self.inst_type}) / get_freq_stop: {float(r):.2f}")
        self.ask(f"SENSE:FREQUENCY:STOP?", callback=callback)
        callback = lambda r: self.outbox.append(f"{self.id} ({self.inst_type}) / get_freq_npoints: {int(r):d}")
        self.ask(f"SENSE:FREQUENCY:POINTS?", callback=callback)

    def snm(self, fname:str, param:str, Npoints:Optional[int]=201) -> None:
        """Sleep a bit then write junk data to the specific file, simulating a S-parameter measurement"""
        callback = lambda x: self.outbox.append(f"{self.id} / {param}: data saved to {fname}")

        self.sleep(5, callback=callback)
        with open(fname, 'w') as f:
            import random
            for i in range(Npoints):
                f.write("{}\n".format(random.uniform(-60, 0)))

    def s11(self, fname:str) -> None:
        """@expose Make S11 measurement and write results to `fname`. NOTE: Toy placeholder. Sleeps for 5 sec, then writes junk."""
        self.snm(fname, 's11')

    def s12(self, fname:str) -> None:
        """@expose Make S12 measurement and write results to `fname`. NOTE: Toy placeholder. Sleeps for 5 sec, then writes junk."""
        self.snm(fname, 's12')

    def s21(self, fname:str) -> None:
        """@expose Make S21 measurement and write results to `fname`. NOTE: Toy placeholder. Sleeps for 5 sec, then writes junk."""
        self.snm(fname, 's21')

    def s22(self, fname:str) -> None:
        """@expose Make S22 measurement and write results to `fname`. NOTE: Toy placeholder. Sleeps for 5 sec, then writes junk."""
        self.snm(fname, 's22')


if __name__ == "__main__":
    rm = ResourceManager('default.yaml@sim')
    rn = 'ASRL2::INSTR'

    interface = AsynchronousInterface(rn, rm, interactive=True)
    interface.idn()
    print(interface.outbox)