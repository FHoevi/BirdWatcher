import cv2
import time
import threading
try:
    from greenlet import getcurrent as get_ident
except ImportError:
    try:
        from thread import get_ident
    except ImportError:
        from _thread import get_ident

GPIO_is_present = False
try:
    import RPi.GPIO as GPIO
    GPIO_is_present = True
except ImportError:
    pass

CAM_INDEX = None
CAM_PARAM = None
PIN = None

if GPIO_is_present:
    CAM_INDEX = 0
    CAM_PARAM = cv2.CAP_V4L
    
    GPIO.setwarnings(False)
    PIN = 18
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN, GPIO.OUT)
else:
    CAM_INDEX = 1
    CAM_PARAM = cv2.CAP_DSHOW

class CameraEvent(object):
    """An Event-like class that signals all active clients when a new frame is available."""
    def __init__(self):
        self.events = {}

    def wait(self):
        """Invoked from each client's thread to wait for the next frame."""
        ident = get_ident()
        if ident not in self.events:
            # this is a new client
            # add an entry for it in the self.events dict
            # each entry has two elements, a threading.Event() and a timestamp
            self.events[ident] = [threading.Event(), time.time()]
        return self.events[ident][0].wait()

    def set(self):
        """Invoked by the camera thread when a new frame is available."""
        now = time.time()
        remove = None

        for ident, event in self.events.items():
            if not event[0].isSet():
                # if this client's event is not set, then set it
                # also update the last set timestamp to now
                event[0].set()
                event[1] = now
            else:
                # if the client's event is already set, it means the client
                # did not process a previous frame
                # if the event stays set for more than 5 seconds, then assume
                # the client is gone and remove it
                if now - event[1] > 5:
                    remove = ident

        if remove:
            del self.events[remove]

    def clear(self):
        """Invoked from each client's thread after a frame was processed."""
        self.events[get_ident()][0].clear()


class Camera():
    thread = None  # background thread that reads frames from camera
    frame = None  # current frame is stored here by background thread
    last_access = 0  # time of last client access to the camera
    event = CameraEvent()

    def __init__(self):
        """Start current circuit for the camera via GPIO.
        Start the background camera thread if it isn't running yet."""
        #GPIO.setmode(GPIO.BCM)
        #GPIO.setup(PIN, GPIO.OUT)

        if Camera.thread is None:
            Camera.last_access = time.time()

            # start background frame thread
            Camera.thread = threading.Thread(target = self._thread)
            Camera.thread.start()

            # wait until first frame is available
            Camera.event.wait()

    def get_frame(self):
        """Return the current camera frame."""
        Camera.last_access = time.time()

        # wait for a signal from the camera thread
        Camera.event.wait()
        Camera.event.clear()

        return Camera.frame

    @staticmethod
    def frames():
        """"Generator that returns frames from the camera.
        Initialize OpenCV camera."""
        camera = cv2.VideoCapture(CAM_INDEX, CAM_PARAM)
        if not camera.isOpened():
            raise RuntimeError('Could not start camera.')

        while True:
            # read current frame
            _, frame = camera.read()

            # encode as a jpeg image and return it
            yield cv2.imencode('.jpg', frame)[1].tobytes()

    @classmethod
    def _thread(cls):
        """Camera background thread."""
        print('Starting camera thread.')
        if GPIO_is_present:
            GPIO.output(PIN, False) # switch ON
        frames_iterator = cls.frames()
        for frame in frames_iterator:
            Camera.frame = frame
            Camera.event.set() #send signal to clients
            time.sleep(0)

            # if there hasn't been any clients asking for frames in
            # the last 10 seconds then stop the thread
            if time.time() - Camera.last_access > 10:
                frames_iterator.close()
                print('Stopping camera thread due to inactivity.')
                Camera.shutdown()
                break
        Camera.thread = None

    @staticmethod
    def shutdown():
        print('Switching hardware off.')

        # Switch off camera current circuit
        if GPIO_is_present:
            GPIO.output(PIN, True)
