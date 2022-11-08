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
