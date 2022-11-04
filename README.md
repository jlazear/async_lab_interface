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
> numpy==1.20.3
>
> PyVISA==1.12.0
>
> PyVISA-sim==0.5.1

The big packages (numpy, PyVISA) are only required for the `controller.py`. The `user_terminal.py` only needs `aio_pika` and `aioconsole`. Split these up in real use. 

Usage
-----
Run `controller.py` in terminal 1.
 > python ./lab_interface/controller.py

 Run `user_terminal.py` in terminal 2.
 > python ./user_terminal/user_terminal.py

 ctrl-c the controller when you're done. 