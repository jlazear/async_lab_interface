#!/bin/bash
echo Starting controller...
python ./lab_interface/controller.py > controller.log 2>&1 &
sleep 2
echo Starting user terminal...
python ./user_terminal/user_terminal.py