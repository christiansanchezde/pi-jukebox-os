#!/usr/bin/env python3
import RPi.GPIO as GPIO
import subprocess

# Setup GPIO
GPIO.setmode(GPIO.BCM)
# Pin 13 for the button, using internal Pull Up resistor
GPIO.setup(13, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Wait for the button (pin 13) to be pulled low (Falling edge)
# This blocks the script until the event happens, taking 0% CPU
GPIO.wait_for_edge(13, GPIO.FALLING)

# Gracefully halt the system
subprocess.call(['shutdown', '-h', 'now'], shell=False)