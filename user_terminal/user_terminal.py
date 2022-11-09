import json
import asyncio
from typing import Optional

import aioconsole
import aio_pika

welcomestr = """

Welcome to the user terminal for this fabulously imaginary lab. Type your command below, or input
    > quit
to quit."""

helpstr = """user_terminal help

Type a command to send to the lab interface
    <id> <cmd> [<arg1> <arg2> ...]
where
    <id> = id of instrument to talk to.
        The only options that will do anything of interest are
            controller   : send a message to the Controller
            1234         : send a message to the VNA (if initialized)
            4321         : send a message to the Power Supply (if initialized)
            abcd         : send a message to the second VNA (if initialized)
            dcba         : send a message to the second Power Supply (if initialized)

    <cmd> = command to send to the target
        Some commands to try for the Controller:
            create_interface <addr> <station> : create a new instrument interface 
                                                valid <addrs> are ASRL22::INSTR, ASRL23::INSTR, ASRL24::INSTR, ASRL25::INSTR
                                                <station> may be any string
            list_instruments                  : list the instruments the Controller is currently controlling
            list_methods                      : interrogate the Controller for what methods are available

        Some commands to try for the Instruments:
            idn                : ask the Instrument who it is
            list_methods       : interrogate the Instrument for what methods are available

        Some (additional) commands to try for the Power Supply:
            set_voltage <V>       : Set the voltage to <V> in Volts. <V> be between 0 and 25. 
            get_voltage           : Get the current voltage in Volts.
            set_output <enable>   : Turn on or off the output. Things evaluating to True are on, evaluating to False are off.
            get_output            : Get the current output state. 

        Some (additional) commands to try for the VNA:
            set_frequency_range <start> <stop> <Npoints>  : Set the frequency range to sample <Npoints:int> 
                                                            from <start:float> to <stop:float> in GHz.
            get_frequency_range                           : Get the current frequency range.
            s11                                           : Make an S11 S-parameter measurement. Not currently implemented!
            s12                                           : Make an S12 S-parameter measurement. Not currently implemented!
            s21                                           : Make an S21 S-parameter measurement. Not currently implemented!
            s22                                           : Make an S22 S-parameter measurement. Not currently implemented!

Some special commands (place into the <id> slot):
    quit - quit out of the program
    help - get this help message
    run <fname> <station> - run a test sequence stored in <fname> on station <station>
"""
stop = False

#TODO instr_dict should be generated from controller.py and database, but haven't implemented DB, so hardcoding
instr_dict = {'station_0': {'powersupply': '4321', 'vna': '1234'},
              'station_1': {'powersupply': 'dcba', 'vna': 'abcd'},
              'raw': {}}

def prettify(d, tabs=0):
    if not isinstance(d, dict):
        return d
    s = '\n'
    for key, value in d.items():
        s += '\t'*tabs + f"{key}: {prettify(value, tabs+1)}\n"
    return s

async def process_response(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        msg = json.loads(message.body)
        print(prettify(msg))

async def consume_task(uri:str="amqp://guest:guest@rabbitmq/", exchange_name:str="e_responses", 
                            queue_name:str="q_responses") -> None:
    print(f"Trying to connect to {uri}")  #DELME
    connection = await aio_pika.connect_robust(uri)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    exchange = await channel.declare_exchange(exchange_name, aio_pika.ExchangeType.FANOUT)
    #TODO check if queue already exists and make another one, so don't stomp
    queue = await channel.declare_queue(queue_name)
    await queue.bind(exchange, '')
    await queue.consume(process_response)
    while not stop:
        await asyncio.sleep(.01)

async def send_message(exchange:aio_pika.Exchange, message:str) -> None:
    cmd_list = message.split()
    try:
        iid, cmd = cmd_list[:2]
    except ValueError:
        print("Invalid command: {cmd_str}")
        print(helpstr)
    args = cmd_list[2:]
    new_args = []
    for arg in args:
        try:
            arg = eval(arg)  #FIXME #TODO eval is wildly unsafe!
        except (NameError, SyntaxError):
            pass
        new_args.append(arg)
    d = {'id': iid,
            'cmd': cmd,
            'args': new_args,
            'kwargs': {}}
    msg = json.dumps(d).encode()
    # print(f"{d = }")  #DELME
    await exchange.publish(aio_pika.Message(body=msg), routing_key='')

async def query_user(exchange:aio_pika.Exchange):
    print(welcomestr)
    global stop
    while not stop:
        line = await aioconsole.ainput('\n> ')
        if not line:
            continue
        cmd_list = line.split()
        if len(cmd_list) == 1:
            cmd = cmd_list[0]
            if cmd.lower() in ('q', 'quit'):
                stop = True
            elif cmd.lower() in ('h', 'help'):
                print(helpstr)
            else:
                print("Invalid command. Did you mean one of these?\n\thelp\n\tquit")
        else:
            if cmd_list[0].lower() in ('r', 'run'):
                try:
                    fname = cmd_list[1]
                    station = cmd_list[2]
                except IndexError:
                    print(f"Invalid run command: {line}")
                    continue
                await run_sequence(fname, station, exchange)
            else:
                await send_message(exchange, line)
        await asyncio.sleep(.2)

async def run_sequence(fname:str, station:str, exchange:aio_pika.Exchange):
    print(f"Running test sequence in {fname}...")
    try:
        with open(fname) as f:
            try:
                instr_dict[station]
            except KeyError:
                print(f"Invalid sequence file! Invalid station name ({station}). Valid station names are {instr_dict.keys()}.")
                return
            for line in f:
                if not line or (line[0] in '#\n\r'):
                    continue
                cmd_list = line.strip().split(maxsplit=1)
                if len(cmd_list) == 1:
                    print(f"Invalid sequence file! Too few arguments on line\n\t{line}")
                    return
                alias = cmd_list[0]
                cmdargs = cmd_list[1]
                if alias.lower() == 'print':
                    print(cmdargs)
                    continue
                if station == 'raw':
                    iid = alias
                else:
                    try:
                        iid = instr_dict[station][alias]
                    except KeyError:
                        print(f"Invalid sequence file! Invalid alias ({alias}). Valid aliases are {instr_dict[station].keys()}.")
                msg = f"{iid} {cmdargs}"
                await send_message(exchange, msg)
    except FileNotFoundError:
        print(f"File not found: {fname}")
        return

async def main(uri:str="amqp://guest:guest@localhost/", send_exchange_name:str="e_queue", rec_exchange_name:str="e_responses", 
                            queue_name:str="q_responses"):
    connection = await aio_pika.connect_robust(uri)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    send_exchange = await channel.declare_exchange(send_exchange_name, aio_pika.ExchangeType.FANOUT)

    await asyncio.gather(consume_task(uri, rec_exchange_name, queue_name), query_user(send_exchange))
    await channel.close()

if __name__ == "__main__":
    import os
    if os.getenv('DOCKER'):
        uri = "amqp://guest:guest@rabbitmq/"
        print(f"Detected you're in a Docker container, using uri = {uri}")
    else:
        uri = "amqp://guest:guest@localhost/"
        print(f"Detected you're not in a Docker container, using uri = {uri}")

    asyncio.run(main(uri))