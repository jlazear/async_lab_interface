import json
import asyncio

import aioconsole
import aio_pika

welcomestr = """

Welcome to the user terminal for this fabulously imaginary lab. Type your command below, or input
    > quit
to quit."""

helpstr = """user_terminal help
********************************************************************************************************
*** WARNING: there's very minimal error handling, so invalid arguments will likely crash everything! ***
********************************************************************************************************

Type a command to send to the lab interface
    <id> <cmd> [<arg1> <arg2> ...]
where
    <id> = id of instrument to talk to.
        The only options that will do anything of interest are
            controller   : send a message to the Controller
            1234         : send a message to the VNA (if initialized)
            4321         : send a message to the Power Supply (if initialized)
        
    <cmd> = command to send to the target
        Some commands to try for the Controller:
            create_interface <addr> <station> : create a new instrument interface 
                                                valid <addrs> are ASRL23::INSTR and ASRL22::INSTR
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
"""
stop = False

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

async def consume_task(uri:str="amqp://guest:guest@127.0.0.1/", exchange_name:str="e_responses", 
                            queue_name:str="q_responses") -> None:
    connection = await aio_pika.connect_robust(uri)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    exchange = await channel.declare_exchange(exchange_name, aio_pika.ExchangeType.FANOUT)
    queue = await channel.declare_queue(queue_name)
    await queue.bind(exchange, '')
    await queue.consume(process_response)
    while not stop:
        await asyncio.sleep(.01)

async def send_message(uri:str="amqp://guest:guest@127.0.0.1/", exchange_name:str="e_queue") -> None:
        connection = await aio_pika.connect_robust(uri)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        exchange = await channel.declare_exchange(exchange_name, aio_pika.ExchangeType.FANOUT)

        print(welcomestr)
        global stop
        while not stop:
            line = await aioconsole.ainput('\n> ')
            if not line:
                continue
            cmd_list = line.split()
            if cmd_list[0].lower() in ('q', 'quit'):
                stop = True
            elif cmd_list[0].lower() in ('h', 'help'):
                print(helpstr)
            else:
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
            await asyncio.sleep(.2)
        await channel.close()

async def main():
    await asyncio.gather(consume_task(), send_message())

if __name__ == "__main__":
    asyncio.run(main())