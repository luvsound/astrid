#!/bin/bash

jack_control start
jack_control ds alsa
jack_control dps device hw:T6
jack_control dps rate 44100
jack_control dps nperiods 3
jack_control dps period 64
