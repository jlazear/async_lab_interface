import functools
from collections import deque
import asyncio
import json
from typing import Optional, Awaitable

import aio_pika

async def process_message(message: aio_pika.abc.AbstractIncomingMessage, queue:deque) -> None:
        async with message.process():
            print(f"receiving msg = {message.body}")
            queue.append(message.body)
            await asyncio.sleep(.01)

def bind_receive_queue(self, queue:deque, uri:str="amqp://guest:guest@127.0.0.1/", exchange_name:str="e_queue", 
                            queue_name:str="q_controller"):
    
    pmsg = functools.partial(process_message, queue=queue)

    async def consume_task() -> None:
        connection = await aio_pika.connect_robust(uri)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        exchange = await channel.declare_exchange(exchange_name, aio_pika.ExchangeType.FANOUT)
        queue = await channel.declare_queue(queue_name, auto_delete=True)
        await queue.bind(exchange, '')
        consumer_tag = await queue.consume(pmsg)

        # Clean up if the controller ever stops
        while not self._stop:
            await asyncio.sleep(1)
        await queue.cancel(consumer_tag)
        await channel.close()

    task = consume_task()
    return task

def bind_send_queue(self, outbox:deque, uri:str="amqp://guest:guest@127.0.0.1/", exchange_name:str="e_responses"):
    async def publish_task() -> None:
        connection = await aio_pika.connect_robust(uri)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        exchange = await channel.declare_exchange(exchange_name, aio_pika.ExchangeType.FANOUT)

        while not self._stop:
            while outbox:
                msg = outbox.popleft()
                print(f"returning {msg = }")  #DELME
                msg = json.dumps(msg).encode()
                await exchange.publish(aio_pika.Message(body=msg), routing_key='')
            await asyncio.sleep(.1)
        await channel.close()
    
    task = publish_task()
    return task

#DELME junk for test
async def wait(queue, t=None):
    if not t:
        i = 0
        while True:
            if i % 10 == 0: print(f"{i = } {len(queue) = }")
            i += 1
            await asyncio.sleep(1)
    else:
        for i in range(t):
            print(f"{i = }")
            await asyncio.sleep(1)
        
async def main2(queue):
    await asyncio.gather(bind_receive_queue(queue), wait(queue))

class Test:
    def __init__(self) -> None:
        self.inbox = deque()

if __name__ == "__main__":
    a = Test()

    asyncio.run(main2(a.inbox))
