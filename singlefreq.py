#!/usr/bin/python

import random

import time
from phue import Bridge
import logging
logging.basicConfig()

b = Bridge('10.1.11.117')

b.connect()

LEFT = 'Hue play L'
RIGHT = 'Hue play R'
CENTER = 'Hue color lamp 1'
ALL = [LEFT, RIGHT, CENTER]

LO_CUT = 600
HI_CUT = 1500

MAX_BRIGHTNESS = 254
MIN_BRIGHTNESS = 100
MAX_HUE = 65534

MAX_FREQUENCY = 20000

LIGHT_THRESHOLD = 0.1

BLEED_OVER = 0.4

INITIAL_HUE = 0
HUE_STEP = 2000

import pyaudio
import numpy as np
np.set_printoptions(suppress=True) # don't use scientific notation

CHUNK = 1024#4096 #* 2 # number of data points to read at a time
RATE = 44100 # time resolution of the recording device (Hz)

p=pyaudio.PyAudio() # start the PyAudio class
stream=p.open(format=pyaudio.paInt16,channels=1,rate=RATE,input=True,
              frames_per_buffer=CHUNK) #uses default input device

maxValue = 2**15
bars = 35

b.set_light(ALL, {'transitiontime': 1, 'on': False})

# Get a dictionary with the light name as the key
light_names = b.get_light_objects('name')
LEFT_OBJ = light_names[LEFT]
CENTER_OBJ = light_names[CENTER]
RIGHT_OBJ = light_names[RIGHT]

light_hue = INITIAL_HUE

def device_response(device_object, normalized_freq, normalized_amplitude):
    global light_hue
    normalized_freq = float(peak_freq) / float(LO_CUT)
    if normalized_amplitude < LIGHT_THRESHOLD:
        device_object.on = False
    else:
        device_object.transitiontime = 1
        device_object.on = True

        clipped_brightness = min(int(MAX_BRIGHTNESS * normalized_amplitude), MAX_BRIGHTNESS)
        floored_brightness = min(clipped_brightness, MIN_BRIGHTNESS)
        device_object.brightness = floored_brightness
        # device_object.hue = random.randint(0, MAX_HUE)# min(int(MAX_HUE * normalized_freq), MAX_HUE)
        device_object.hue = light_hue
        device_object.transitiontime = 30
        device_object.brightness = 0
        device_object.on = False

        light_hue = (light_hue + HUE_STEP) % MAX_HUE

# create a numpy array holding a single read of audio data
#for i in range(50): #to it a few times just to see
while True:
    try:
        stream_value = stream.read(CHUNK)
    except IOError as ex:
        # if ex[1] != pyaudio.paInputOverflowed:
        #     raise
        # stream_value = '\x00' * CHUNK  # or however you choose to handle it, e.g. return None
        # stream.stop_stream()
        stream.close()
        p.terminate()
        p=pyaudio.PyAudio() # start the PyAudio class
        stream=p.open(format=pyaudio.paInt16,channels=1,rate=RATE,input=True,
                      frames_per_buffer=CHUNK) #uses default input device
        stream_value = stream.read(CHUNK)

    data = np.fromstring(stream_value,dtype=np.int16)
    data = data * np.hanning(len(data)) # smooth the FFT by windowing data

    fft = abs(np.fft.fft(data).real)
    fft = fft[:int(len(fft)/2)] # keep only first half
    freq = np.fft.fftfreq(CHUNK,1.0/RATE)
    freq = freq[:int(len(freq)/2)] # keep only first half
    peak_freq = freq[np.where(fft==np.max(fft))[0][0]]+1

    dataL = data[0::2]
    dataR = data[1::2]
    peakL = np.abs(np.max(dataL)-np.min(dataL))/float(maxValue)
    peakR = np.abs(np.max(dataR)-np.min(dataR))/float(maxValue)
    print(peakL)
    lString = "#"*int(peakL*bars)+"-"*int(bars-peakL*bars)
    rString = "#"*int(peakR*bars)+"-"*int(bars-peakR*bars)
    print("L=[%s]\tR=[%s]\tF=[%s]"%(lString, rString, int(peak_freq)))

    amplitude = (peakL + peakR) / float(2)
    normalized_amplitude = amplitude #/ float(maxValue)

    if peak_freq < LO_CUT * (1 + BLEED_OVER):
        normalized_freq = float(peak_freq) / float(LO_CUT)
        device_response(LEFT_OBJ, normalized_freq, normalized_amplitude)
        # if normalized_amplitude < 0.4:
        #     LEFT_OBJ.on = False
        # else:
        #     LEFT_OBJ.on = True
        #     LEFT_OBJ.brightness = int(MAX_BRIGHTNESS * normalized_amplitude)
        #     LEFT_OBJ.hue = int(MAX_HUE * normalized_freq)
    if peak_freq >= LO_CUT * (1 - BLEED_OVER) and peak_freq <= HI_CUT * (1 + BLEED_OVER):
        normalized_freq = float(peak_freq - LO_CUT) / float(HI_CUT - LO_CUT)
        device_response(CENTER_OBJ, normalized_freq, normalized_amplitude)
        # if normalized_amplitude < LIGHT_THRESHOLD:
        #     CENTER_OBJ.on = False
        # else:
        #     CENTER_OBJ.on = True
        #     CENTER_OBJ.brightness = int(MAX_BRIGHTNESS * normalized_amplitude)
        #     CENTER_OBJ.hue = int(MAX_HUE * normalized_freq)
    if peak_freq > HI_CUT * (1 - BLEED_OVER):
        normalized_freq = float(peak_freq - HI_CUT) / float(MAX_FREQUENCY - HI_CUT)
        device_response(RIGHT_OBJ, normalized_freq, normalized_amplitude)
        # if normalized_amplitude < LIGHT_THRESHOLD:
        #     RIGHT_OBJ.on = False
        # else:
        #     RIGHT_OBJ.on = True
        #     RIGHT_OBJ.brightness = int(MAX_BRIGHTNESS * normalized_amplitude)
        #     RIGHT_OBJ.hue = int(MAX_HUE * normalized_freq)
    # print(peak_freq)


# close the stream gracefully
stream.stop_stream()
stream.close()
p.terminate()
