import tuner
import squitter
import basic
import Queue
import threading
import curses
import logging
import logging.handlers
import time
import sys

"""
This module implements the application using 2 classes

1. Radar, it runs in a separate thread, reads from a message queue, decode messages and adds to a display queue
   The display queue is read recurrently (once per sec) from a RepeatTimer thread and is displayed

2. TextDisplay, implements a text table format using curses. It reads quitter objects and format the output.

The main application initiates a tuner object and a radar object. The tuner runs the main thread and passes
information to the radar object through a callback function (Radar - tuner_read).

The tuner_read method creates a Squitter object, do some basic parsing of the message and stores it into a 
message queue (msgQ). The message passed from the tuner is in the format 

    [[signal strength (float), message (long)], [signal strength, message], ...]
    
    signal strength is a simple measure of (max sample - min sample) in the preamble divided by max range (65535)
    expressed in %. Thus signal_strength = 10 means that the diff of 'max sample' and 'min sample' is 10% of the
    dynamic range.
    
    message is the signal found by the tuner encoded as a long integer. 
    
The radar object pick up the basic Squitter objects from the message queue (msgQ), decodes it further 
(using Squitter.py) and store the resulting Squitter object into a 'blip dictionary' using the ICAO information as key.

The blip dictionary have the following format

    {ICAO24: [{'timestamp': ts, 'cnt': n, 'msg': message}, ...]}
    'timestamp' is when the message was seen, 
    'cnt' is how many times a message have been seen,
    'msg' is the decoded Squitter object

The blip dictionary is in turn read recurrently by a separate thread for display.
"""


class TextDisplay:
    """
    This implements a table text display for Squitter messages using curses
    
    Methods are:
        add: add a new message + timestamp + count into the msgQ dictionary using ICAO address as key
             The methods also traverse the msqQ objects to propagate message items to the latest on
        start: initialize the window environment
        update_screen: format and add strings to the window form the msgQ
        close: close the window environment in an orderly manner
    """
    def __init__(self):
        self.msgQ = {}

        # header is on the format [Column, String]
        self.header_text = [[0, "ICAO"], [8, "Mode"], [14, "Sqwk"], [20, "Flight"], [29, "Alt"], [36, "Spd"],
                            [41, "Hdg"], [48, "Lat"], [57, "Long"], [64, "Sig%"], [70, "Msgs"], [77, "Ti "]]
        self.last_pos = self.header_text[-1][0] + len(self.header_text[-1][1])
        self.header_underline = "-"*self.last_pos
        self.header_spinner = "|/-\\"
        self.update_cnt = 0
        self.win = None
        self.max_row = 0
        self.saved_cur = None
        curses.wrapper(self.start)

    def start(self, screen):
        self.win = screen
        self.saved_cur = curses.curs_set(0)
        self.max_row = self.win.getmaxyx()[0]
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
        self.update_screen()

    def update_screen(self):
        self.win.clear()

        for ind in self.header_text:
            self.win.addstr(0, ind[0], ind[1])
        self.win.addch(0, self.last_pos, self.header_spinner[self.update_cnt % 4])
        self.win.addstr(1, 0, self.header_underline)
        self.update_cnt += 1

        row = 2
        for key in self.msgQ.keys():
            for msg in self.msgQ[key]['msg']:
                self.win.addstr(row, self.header_text[0][0], msg.ICAO24, curses.color_pair(3))
                self.win.clrtoeol()
                if msg.downlink_format != 0:
                    self.win.addstr(row, self.header_text[1][0], str(msg.downlink_format), curses.color_pair(3))
                if msg.Squawk != 0:
                    self.win.addstr(row, self.header_text[2][0], "{:=04X}".format(msg.Squawk), curses.color_pair(3))
                if msg.call_sign != "":
                    self.win.addstr(row, self.header_text[3][0], msg.call_sign, curses.color_pair(3))
                if msg.altitude != 0:
                    self.win.addstr(row, self.header_text[4][0], str(int(round(msg.altitude))), curses.color_pair(3))
                if msg.velocity != 0:
                    self.win.addstr(row, self.header_text[5][0], str(int(round(msg.velocity))), curses.color_pair(3))
                if msg.heading != 0:
                    self.win.addstr(row, self.header_text[6][0], str(int(round(msg.heading))), curses.color_pair(3))
                if msg.latitude != 0:
                    self.win.addstr(row, self.header_text[7][0], str(round(msg.latitude, 3)), curses.color_pair(3))
                if msg.longitude != 0:
                    self.win.addstr(row, self.header_text[8][0], str(round(msg.longitude, 3)), curses.color_pair(3))
                if msg.signal_strength != 0:
                    self.win.addstr(row, self.header_text[9][0], str(msg.signal_strength), curses.color_pair(3))

            self.win.addstr(row, self.header_text[10][0], str(self.msgQ[key]['msg_count']), curses.color_pair(2))
            self.win.addstr(row, self.header_text[11][0], str(self.msgQ[key]['timestamp']), curses.color_pair(1))

            row += 1

        self.win.refresh()

    def clear_queue(self):
        self.msgQ = {}

    def add(self, ts, msg, cnt):
        # msgQ = {'abc': {'msg': [squitter1, squitter2, ...], 'timestamp': 0, 'msg_count': 1}, 'def':
        if msg.ICAO24 in self.msgQ:
            self.msgQ[msg.ICAO24]['msg'].append(msg)
            self.msgQ[msg.ICAO24]['timestamp'] = str(int(time.time() - ts))
            self.msgQ[msg.ICAO24]['msg_count'] = cnt
        else:
            self.msgQ[msg.ICAO24] = {}
            self.msgQ[msg.ICAO24]['msg'] = [msg]
            self.msgQ[msg.ICAO24]['timestamp'] = str(int(time.time() - ts))
            self.msgQ[msg.ICAO24]['msg_count'] = cnt

        # Scan list for call sign and Squawk information and copy this to new list items
        # If we don't do this the information will be lost when we remove the item

        for key in self.msgQ.keys():
            call_sign = ""
            velocity = altitude = heading = squawk = latitude = longitude = 0
            for item in self.msgQ[key]['msg']:
                if item.call_sign != "":
                    call_sign = item.call_sign
                item.call_sign = call_sign
                if item.Squawk != 0:
                    squawk = item.Squawk
                item.Squawk = squawk
                if item.velocity != 0:
                    velocity = item.velocity
                item.velocity = velocity
                if item.altitude != 0:
                    altitude = item.altitude
                item.altitude = altitude
                if item.heading != 0:
                    heading = item.heading
                item.heading = heading
                if item.latitude != 0:
                    latitude = item.latitude
                item.latitude = latitude
                if item.longitude != 0:
                    longitude = item.longitude
                item.longitude = longitude

        if len(self.msgQ) == self.max_row - 2:
            del self.msgQ[msg.ICAO24]

    def close(self):
        curses.curs_set(self.saved_cur)
        curses.endwin()


class Radar(basic.ADSB, threading.Thread):
    """
    The Radar class is where squitter messages are stored and processed.
    It implements a Queue (msgQ) where parsed squitter messages from the tuner are stored for processing.

    Radar run through its own thread where the main loop (run) gets messages from msQ
    
    The tuner_read method are a callback used by the tuner, this method is executed from the Tuner thread.
    
    As messages are processed from the Queue they are stored into a dictionary (blips)  using the ICAO address as index.
    Messages in the dictionary have a timestamp and messages older than MAX_MSG_LIFETIME (seconds) are removed.
    When messages are refreshed the timestamp are updated.
    
    The radar use a Text User Interface (TUI) to display information to the end user.
    """

    def __init__(self):
        threading.Thread.__init__(self, name="Radar")

        self.lock = threading.Lock()
        self.finished = threading.Event()

        self.msgQ = Queue.Queue()  # msgQ is where we store messages that the tuner have detected, unlimited queue size
        self.blips = {}  # blips is a dictionary where we keep the recently seen messages
        self.screen = None

        self.daemon = True  # This is a daemon thread
        self.logger = logging.getLogger('spots.Radar')
        self.blip_timer = basic.RepeatTimer(1, self._scan_blips, "Radar blip timer")
        self.blip_timer.start()

    def _scan_blips(self):
        """
        Scan the blip dictionary and add to the screen (if used) or print the item if screen not used
        Note that the access to the blip dictionary is locked to prevent the producer thread to modify it
        """
        self.lock.acquire()
        self._remove_old_blips()

        for key in self.blips.keys():
            for item in self.blips[key]:
                if self.cfg_use_text_display:
                    self.screen.add(item['timestamp'], item['msg'], item['count'])
                else:
                    print item['msg']

        self.lock.release()
        if self.cfg_use_text_display:
            self.screen.update_screen()
            self.screen.clear_queue()

    def _remove_old_blips(self):
        """
        Remove blips that has a timestamp older than specified level (normally 60 secs)
        """
        for key in self.blips.keys():
            ind = 0
            for item in self.blips[key]:
                if (time.time() - item['timestamp']) >= self.cfg_max_blip_ttl:
                    del self.blips[key][ind]
                ind += 1
            if not self.blips[key]:
                del self.blips[key]

    def _blip_add(self, msg):
        """
        Decdode and add msg to the blips dictionary with a timestamp using ICAO address as key.
        If an entry on the ICAO address exists, append the element. If it does not exists, create a new list.
        
        Note that a lock is needed before the blip dictionary is modified to avoid confusing the reader thread
        """
        msg.decode()
        self.lock.acquire()
        # blip: {ICAO24: [{'timestamp': ts, 'count': n, 'msg': msg}, {'timestamp: ts, ...}]}
        if msg.ICAO24 in self.blips:
            item = {'timestamp': time.time(), 'count': self.blips[msg.ICAO24][-1]['count'] + 1, 'msg': msg}
            self.blips[msg.ICAO24].append(item)
        else:
            item = {'timestamp': time.time(), 'count': 1, 'msg': msg}
            self.blips[msg.ICAO24] = [item]

        # Decode latitude and longitude by finding 2 frames, 1 with odd CPR format + 1 with even CPR format
        for key in self.blips.keys():
            odd_msg = even_msg = None
            for item in self.blips[key]:
                if item['msg'].is_CPR():
                    if item['msg'].is_odd_CPR():
                        odd_msg = item['msg']
                    else:
                        even_msg = item['msg']
                    if (even_msg is not None) and (odd_msg is not None):
                        result = squitter.decodeCPR(odd_msg, even_msg)
                        if result is not None:
                            item['msg'].add_lat_long(result['latitude'], result['longitude'])
                        else:
                            result = squitter.decodeCPR_relative(odd_msg, even_msg)
                            if result is not None:
                                item['msg'].add_lat_long(result['latitude'], result['longitude'])

        self.lock.release()
        if self.cfg_verbose_logging:
            self.logger.info("{}".format(str(msg)))

    def _blip_exist(self, msg):
        return msg.ICAO24 in self.blips

    def run(self):
        """
        Main loop for the Radar object, here is were objects from the tuner is retrieved and checked before
        adding to the blip dictionary.
        
        Note that the crc is checked here versus different type of messages. 
        Messages are added to the blip dictionary if:
        1. The crc is ok
        2. If crc is not ok, check if the the ICAO address exists in blip dictionary and add
            a. if msg is of type 11 and crc sum is less than 80
            b. we try setting the ICAO address to the crc sum for other messages, for these messages the
               ICAO address is xor'ed with the crc
        """
        self.logger.info("Radar running")

        if self.cfg_use_text_display:
            self.screen = TextDisplay()

        while not self.finished.is_set():
            msg = self.msgQ.get()
            if msg.downlink_format == self.DF_ALL_CALL_REPLY_11:
                if msg.crc_ok:
                    self._blip_add(msg)
                else:
                    if basic.ADSB.crc_2_int(msg.crc_sum) < 80 and self._blip_exist(msg):
                        msg.crc_ok = True
                        self._blip_add(msg)
            elif (msg.downlink_format == self.DF_ADSB_MSG_17 or msg.downlink_format == self.DF_EXTENDED_SQUITTER_18) \
                    and msg.crc_ok:
                self._blip_add(msg)
            else:  # All other DF have CRC xor'ed with ICAO address
                if msg.crc_ok:
                    self._blip_add(msg)
                else:
                    # we use the crc_sum for ICAO, this is tested in the decode method of Squitter
                    msg.ICAO24 = msg.crc_sum
                    msg.crc_ok = True if self._blip_exist(msg) else False
                    if msg.crc_ok:
                        self._blip_add(msg)

        self.logger.info("Radar stopping")

    def _die(self):
        self.logger.info("Radar dying")

        self.finished.set()
        self.blip_timer.cancel()
        if self.cfg_use_text_display:
            self.screen.close()

    def tuner_read(self, msgs, stop=False):
        """
        Callback function used by the tuner thread (which is the main thread)
        Creates a new Squitter object and do some basic parsing, add to the msgQ
        """
        if stop:
            self._die()
        else:
            for m in msgs:
                sq = squitter.Squitter()
                sq.parse(m)
                if sq.msg != 0:
                    self.msgQ.put(sq)


def main():
    print "Spots version {}".format(basic.ADSB.VERSION)

    sys.stderr = open("spots.err", 'w')
    logger = logging.getLogger('spots')
    logger.setLevel(logging.DEBUG)
    fh = logging.handlers.RotatingFileHandler(filename=basic.ADSB.cfg_log_file,
                                              mode='w',
                                              maxBytes=basic.ADSB.cfg_log_max_bytes,
                                              backupCount=basic.ADSB.cfg_log_backup_count)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    fh.setLevel(logging.DEBUG)

    logger.info("Spots version: {}".format(basic.ADSB.VERSION))

    if basic.ADSB.cfg_read_from_file:
        tuner1090 = tuner.Tuner(filename=basic.ADSB.cfg_file_name)
    else:
        tuner1090 = tuner.Tuner()

    tuner1090.start()

    radar = Radar()
    radar.start()

    tuner1090.read(radar.tuner_read)  # This is the main loop and main thread


if __name__ == '__main__':
    main()
