asynchronous_lab_interface
==========================

An asynchronous interface for working with laboratory instruments.

Requirements
------------
Python >=3.9.7 (lower would probably work, but only tested on 3.9.7)
RabbitMQ server must be installed and running on amqp://guest:guest@127.0.0.1:15672/

Python packages
> aio_pika==8.2.4
>
> aioconsole==0.5.1
>
> PyVISA==1.12.0
>
> PyVISA-sim==0.5.1

The big packages (~~numpy~~, PyVISA) are only required for the `controller.py`. The `user_terminal.py` only needs `aio_pika` and `aioconsole`. Split these up in real use. 

Usage
-----
 ### Running from docker
 Clone this repo, then in the main directory run
 > docker-compose run async_lab_interface

 Wait ~30 seconds for the rabbitmq server to spin up in the background, then start the lab interface with
 > ./run.sh

### Running manually
Start up rabbitmq. If you're using Docker for this:
> docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:management

Note that rabbitmq takes a bit to start up, so wait ~30 seconds before proceeding. You can check if
rabbitmq is running by looking for its management portal:
> http://localhost:15672

Run `controller.py` in terminal 1.
 > python ./lab_interface/controller.py
 
(or alternatively in the background by appending a `&`).

 Run `user_terminal.py` in terminal 2.
 > python ./user_terminal/user_terminal.py

 ctrl-c the controller when you're done.

 Then shutdown rabbitmq if unneeded
 > docker ps
 >
 > docker stop <unique hash fragment of rabbitmq container>

Demo
====
A sequence of commands to see functionality (`#` indicates a comment)

~~~
# nothing is connected
> controller list instruments
No instruments connected!

# interrogate the controller
> controller list_methods
create_interface:
        signature: create_interface(resource_name: str, station_name: str) -> interface.AsynchronousInterface
        docstring: Add a new instrument to the controller, at the specified `resource_name` and `station_name`
[...]

# connect the instruments into 2 stations (station_0 and station_1)
> controller create_interface ASRL22::INSTR station_0
controller / create_interface: VNA (1234) [station_0] @ ASRL22::INSTR

> controller create_interface ASRL23::INSTR station_0
controller / create_interface: PowerSupply (4321) [station_0] @ ASRL23::INSTR

> controller create_interface ASRL24::INSTR station_1
controller / create_interface: VNA (abcd) [station_1] @ ASRL24::INSTR

> controller create_interface ASRL25::INSTR station_1
controller / create_interface: PowerSupply (dcba) [station_1] @ ASRL25::INSTR

# the instruments
> controller list_instruments
1234: ['station_0', 'ASRL22::INSTR', 'VNA']
4321: ['station_0', 'ASRL23::INSTR', 'PowerSupply']
abcd: ['station_1', 'ASRL24::INSTR', 'VNA']
dcba: ['station_1', 'ASRL25::INSTR', 'PowerSupply']

# interrogate an instrument for its commands
> 4321 list_methods
ask:
        signature: ask(cmd: str, callback: Optional[Callable[..., NoneType]] = None) -> None
        docstring: Ask (write then read response) of command `cmd`

get_output:
        signature: get_output(enable: bool = True) -> None
        docstring: Get the current output state

get_voltage:
        signature: get_voltage() -> None
        docstring: Get the voltage in V

# send commands to instruments and get back responses
> 4321 idn
4321 / idn: PowerSupply-4321

> 1234 idn
1234 / idn: VNA-1234

# send commands quickly... show that the sleep command (simulates a long-running command)
# blocks station_0, but does not block station_1
> 4321 set_voltage 5.2
> 1234 sleep 15
> 4321 get_voltage
> abcd idn

# Execute some test sequences in parallel
> run example_test.txt station_0
> run example_test.txt station_1
~~~