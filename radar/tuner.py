import basic
import Queue
import logging
import math
import struct
import threading
import rtlsdr
import time

__author__ = 'Wolfrax'

"""
A Software Defined Radio (SDR) module reading IQ samples from a HW tuner and detects ADS-B messages

This module have one object - Tuner, when initialized it create an RtlSdr object using the pyrtlsdr library
The pyrtlsdr library is a wrapper for rtlsdr.
See http://osmocom.org/projects/sdr/wiki/rtl-sdr and https://github.com/roger-/pyrtlsdr

When the tuner is started it runs as a separate thread that detects squitter messages, these are added
to an internal message queue for others to consume. As the queue is limited it will raise an exception
when the queue is full.
The consumer thread uses the tuner read methods to get queued messages
"""


class Tuner(basic.ADSB, threading.Thread):
    """
    The tuner reads samples from a physical tuner (sdr) or from file in an own thread
    
    IQ samples are returned in a callback function where they are
    1. converted to unsigned bytes
    2. scaled to range 0 to 65535
    3. used to detect the preamble
    4. stored into the data-queue if a valid preamble is found
    
    Another thread use the read method to retrieve the samples stored in the data-queue for further processing
    """
    def __init__(self, sr=2.0e6, cf=1090e6, gain='max', filename=None):
        threading.Thread.__init__(self, name="Tuner")
        basic.ADSB.__init__(self)

        self.finished = threading.Event()

        self.daemon = True
        self.logger = logging.getLogger('spots.Tuner')

        self.logger.info("Tuner initializing")

        if filename is None:
            self.sdr = rtlsdr.RtlSdr()
            self.sdr.DEFAULT_ASYNC_BUF_NUMBER = self.MODES_ASYNC_BUF_NUMBER

            self.sdr.sample_rate = sr
            self.sdr.center_freq = cf
            self.sdr.gain = max(self.sdr.get_gains()) if gain == 'max' else gain
            self.sdr.set_agc_mode(0)
            self.logger.info("Tuner initialised to gain {}".format(self.sdr.gain))

        self.data = Queue.Queue(self.MODES_ASYNC_BUF_NUMBER)
        self._cb_func = None

        # Each I and Q value varies from 0 to 255, which represents a range from -1 to +1. To get from the
        # unsigned (0-255) range you therefore subtract 127 from each I and Q, giving you
        # a range from -127 to +128
        #
        # To decode the AM signal, you need the magnitude of the waveform, which is given by sqrt((I^2)+(Q^2))
        # The most this could be is if I&Q are both 128, so you could end up with a magnitude
        # of 181.019
        #
        # However, in reality the magnitude of the signal should never exceed the range -1 to +1, because the
        # values are I = rCos(w) and Q = rSin(w). Therefore the integer computed magnitude should never
        # exceed 128
        #
        # If we scale up the results so that they range from 0 to 65535 (16 bits) then we need to multiply
        # by 511.99.
        #
        # So lets see if we can improve things by subtracting 127.5, Well in integer arithmetic we can't
        # subtract half, so, we'll double everything up and subtract one, and then compensate for the doubling
        # in the multiplier at the end.
        #
        # If we do this we can never have I or Q equal to 0 - they can only be as small as +/- 1.
        # This gives us a minimum magnitude of root 2 (0.707), so the dynamic range becomes (1.414-255). This
        # also affects our scaling value, which is now 65535/(255 - 1.414), or 258.433254
        #
        # The sums then become mag = 258.433254 * (sqrt((I*2-255)^2 + (Q*2-255)^2) - 1.414)
        #                   or mag = (258.433254 * sqrt((I*2-255)^2 + (Q*2-255)^2)) - 365.4798
        #
        # We also need to clip the lookup table just in case any rogue I/Q values somehow do have a
        # magnitude greater than 255.
        #

        self.LUT = [[int(round(258.433254 * math.sqrt((i * 2 - 255) ** 2 + (q * 2 - 255) ** 2) - 365.4798))
                     for q in range(256)] for i in range(256)]
        self.LUT = [map((lambda x: x if x < self.MODES_SIGMAX else self.MODES_SIGMAX), elem) for elem in self.LUT]

        self.filename = filename
        self.sig = []

        if self.filename is not None:
            with open(self.filename, "r") as f:
                iq = f.read(1)
                while iq != "" and len(self.sig) < self.MODES_DATA_LEN:
                    self.sig.append(struct.unpack('B', iq)[0])
                    iq = f.read(1)

        self.logger.info("Tuner initializing done")

    def _iq_to_uint(self, sig):
        return [self.LUT[sig[ind] / 256][sig[ind] % 256] for ind in range(len(sig))]

    def run(self):
        self.logger.info("Tuner start reading")

        if self.filename is None:
            # DEFAULT_ASYNC_BUF_NUMBER is the number of elements in the ring buffer within librtlsdr c-implementation
            # pyrtlsdr sets this to 15. This means that the callback function (signal) is called
            # MODES_ASYNC_BUF_NUMBER (16) times before it starts to overwriting the first buffer in the ring
            # The read_samples_async is a blocking function from where the callback function is called,
            # cancel_read_async needs to be called to return from read_samples_async.

            # self.sdr.read_samples_async(self._sdr_cb, num_samples=self.MODES_DATA_LEN)
            self.sdr.read_bytes_async(self._sdr_cb, num_bytes=self.MODES_DATA_LEN)
        else:
            self._sdr_cb(self.sig, None)

    def _sdr_cb(self, samples, context):
        try:
            # Samples are returned as unsigned bytes with i-value followed by q-value
            # Below we we create an unsigned short with i-value in the MSB followed q-value in LSB

            samples = [((samples[ind+1] << 8) | samples[ind]) for ind in range(0, len(samples) - 1, 2)]
            samples = self._iq_to_uint(samples)

            adsb_samples = self._detect_adsb(samples)  # This is where we scan for the preamble
            basic.statistics['valid_preambles'] += len(adsb_samples)
            self.data.put(adsb_samples)

        except Queue.Full:
            self.logger.error('Queue is full!')
            self.die()

    def die(self):
        self.logger.info("Tuner dying...")
        self.finished.set()
        if self._cb_func is not None:
            self._cb_func(None, stop=True)
        if self.filename is None:
            self.sdr.cancel_read_async()

        self.logger.info(str(basic.statistics))

    def read(self, cb_func):
        self._cb_func = cb_func
        try:
            while not self.finished.is_set():
                try:
                    msgs = self.data.get(timeout=1.0)  # Timeout after 1 sec to ensure we are not blocked forever
                except Queue.Empty:
                    continue  # So we got a timeout from the Queue, continue to execute

                self._cb_func(msgs)

                if not self.cfg_run_as_daemon:
                    # If we are reading from file, sleep for 2 secs to allow for printout, then raise exception and die
                    if self.cfg_read_from_file and not self.cfg_use_text_display:
                        time.sleep(2)
                        self.die()
        except KeyboardInterrupt:
            self.die()
