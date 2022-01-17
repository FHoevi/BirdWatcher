#!/usr/bin/env python
from flask import Flask, render_template, Response
from camera.camera import Camera

GPIO_is_present = False
try:
    import RPi.GPIO as GPIO
    GPIO_is_present = True
except ImportError:
    pass

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(Camera()), mimetype = 'multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug = True)

    if GPIO_is_present:
        GPIO.cleanup()
