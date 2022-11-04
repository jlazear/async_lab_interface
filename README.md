asynchronous_lab_interface
==========================

An asynchronous interface for working with laboratory instruments.

Requirements
------------
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

Usage
-----
Run `controller.py` in terminal 1.
 > python ./lab_interface/controller.py

 Run `user_terminal.py` in terminal 2.
 > 