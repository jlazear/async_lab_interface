# syntax=docker/dockerfile:1

FROM python:3.9-alpine

WORKDIR /usr/src/app

RUN apk add --no-cache --update \
    python3 python3-dev gcc \
    gfortran musl-dev \
    libffi-dev openssl-dev
RUN apk add --no-cache bash

RUN pip install --upgrade pip

ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python3 -m venv $VIRTUAL_ENV \
    && pip3 install --no-cache-dir \
        numpy==1.20.3

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# CMD "echo \"step 1\""
# CMD "sleep 5"
# CMD "echo \"step 2\""

CMD [ "python", "./lab_interface/controller.py" , "&"]
CMD [ "python", "./user_terminal/user_terminal.py"]