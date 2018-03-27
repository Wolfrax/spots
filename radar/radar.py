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
import server
import operator
import os
import simplejson

__author__ = 'Wolfrax'

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

To collect some (rather pointless) statistics using call signs counts a smple FlightDB class exists.
Call sign statistics is stored into a json structure which is stored recurrently on file (file name is configurable in 
the config file, if "flight db name" is "" this function is not used).
A simple tool to dump the content of the file exists (flight_db_tool.py), A client can ask for this information using
"GET FLIGHT_DB STR" (implemented in server.py).
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
        self.header_underline = "-" * self.last_pos
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
        self.win.clrtobot()
        self.update_cnt += 1

        row = 2
        for key in self.msgQ.keys():
            msg = self.msgQ[key]['msg']
            self.win.addstr(row, self.header_text[0][0], msg['ICAO24'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[1][0], msg['downlink_format'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[2][0], msg['squawk'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[3][0], msg['call_sign'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[4][0], msg['altitude'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[5][0], msg['velocity'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[6][0], msg['heading'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[7][0], msg['latitude'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[8][0], msg['longitude'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[9][0], msg['signal_strength'], curses.color_pair(3))
            self.win.addstr(row, self.header_text[10][0], self.msgQ[key]['msg_count'], curses.color_pair(2))
            self.win.addstr(row, self.header_text[11][0], self.msgQ[key]['timestamp'], curses.color_pair(1))

            row += 1

        self.win.refresh()

    def clear_queue(self):
        self.msgQ = {}

    def add(self, ts, msg, cnt):
        # msgQ = {'abc': {'msg': squitter, 'timestamp': '0', 'msg_count': '1'}, 'def':...
        icao = msg['ICAO24']
        if icao in self.msgQ:
            self.msgQ[icao]['msg'].update(msg)
        else:
            self.msgQ[icao] = {}
            self.msgQ[icao]['msg'] = msg

        self.msgQ[icao]['timestamp'] = str(int(time.time() - ts))
        self.msgQ[icao]['msg_count'] = str(cnt)

        if len(self.msgQ) == self.max_row - 2:
            del self.msgQ[icao]

    def close(self):
        curses.curs_set(self.saved_cur)
        curses.endwin()


class FlightDB:
    """
    The FlightDB class is a simple persistent storage of flight data.

    It stores data int a json file and sends the flights to the client
    """

    def __init__(self, loc):
        location = os.path.expanduser(loc)
        self.loc = loc
        init_db = {'version': basic.ADSB.VERSION,
                   'start_date': basic.statistics['start_time_string'],
                   'total_cnt': 0,
                   'flights': {}}

        if os.path.exists(location):
            try:
                self.db = simplejson.load(open(self.loc, 'rb'))
            except simplejson.JSONDecodeError:
                self.db = init_db
        else:
            self.db = init_db
        self.dump()

    def add(self, flight):
        if flight in self.db['flights']:
            self.db['flights'][flight] += 1
        else:
            self.db['flights'][flight] = 1
        self.db['total_cnt'] += 1

    def get_head(self):
        return {k: v for k, v in self.db.iteritems() if k in ('version', 'start_date', 'total_cnt')}

    def get_flights(self):
        # Return a sorted dictionary of flights, descending order
        # See https://stackoverflow.com/questions/613183/how-do-i-sort-a-dictionary-by-value
        return {'flights': sorted(self.db['flights'].items(), key=operator.itemgetter(1), reverse=True)}

    def dump(self):
        with open(self.loc, 'wt') as f:
            simplejson.dump(self.db, f, skipkeys=True, indent=4*' ')


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

        if basic.ADSB.cfg_use_flight_db:
            # We create a simple persistent storage for counting of flights
            self.flight_db = FlightDB(basic.ADSB.cfg_flight_db_name)
            self.flight_db.dump()
            self.flight_timer = basic.RepeatTimer(10 * 60, self._dump_flight_db, "Radar flight DB timer")
            self.flight_timer.start()

        self.blip_timer = basic.RepeatTimer(1, self._scan_blips, "Radar blip timer")
        self.stat_timer = basic.RepeatTimer(3600, self._show_stats, "Radar stat timer")
        self.blip_timer.start()
        self.stat_timer.start()

    def _dump_flight_db(self):
        if basic.ADSB.cfg_use_flight_db:
            # Save to persistent storage, flights and statistics
            self.logger.info("Dumping DB to file")
            self.flight_db.dump()

    def _show_stats(self):
        self.logger.info("Dumping statistics to file")
        self.logger.info(str(basic.statistics))

    def get_flight_db(self):
        if basic.ADSB.cfg_use_flight_db:
            fl = self.flight_db.get_head()
            fl.update(self.flight_db.get_flights())
        else:
            fl = {}
        return fl

    @staticmethod
    def get_statistics():
        return basic.statistics.data

    def get_blips_serialized(self):
        # blips_series: {{'count': x, 'timestamp': y, 'altitude': 0, 'longitude': 13.755, ...},
        #                {'count': y, ...}}

        result = []
        self.lock.acquire()

        for key in self.blips.keys():
            elem = {'count': self.blips[key]['count'],
                    'timestamp': str(int(time.time() - self.blips[key]['timestamp']))}
            for msg_key in self.blips[key]['msg']:
                elem.update({msg_key: self.blips[key]['msg'][msg_key]})
            result.append(elem)

        self.lock.release()
        return result

    def _scan_blips(self):
        """
        Scan the blip dictionary and add to the screen (if used) or print the item if screen not used
        Note that the access to the blip dictionary is locked to prevent the producer thread to modify it
        """
        self.lock.acquire()
        self._remove_old_blips()

        for key in self.blips.keys():
            if self.cfg_use_text_display:
                self.screen.add(self.blips[key]['timestamp'], self.blips[key]['msg'], self.blips[key]['count'])
            else:
                print self.blips[key]['msg']

        self.lock.release()
        if self.cfg_use_text_display:
            self.screen.update_screen()
            self.screen.clear_queue()

    def _remove_old_blips(self):
        """
        Remove blips that has a timestamp older than specified level (normally 60 secs)
        """
        for key in self.blips.keys():
            if (time.time() - self.blips[key]['timestamp']) >= self.cfg_max_blip_ttl:
                del self.blips[key]

    def _blip_add(self, msg):
        """
        Decdode and add msg to the blips dictionary with a timestamp using ICAO address as key.
        If an entry on the ICAO address exists, update the element.

        Note that a lock is needed before the blip dictionary is modified to avoid confusing the reader thread
        """
        msg.decode()
        icao = msg['ICAO24']
        self.lock.acquire()
        # blip: {ICAO24: {'timestamp': ts, 'count': n, 'msg': msg},...}
        if icao in self.blips:
            self.blips[icao]['msg'].update(msg)
            self.blips[icao]['timestamp'] = time.time()
            self.blips[icao]['count'] += 1
        else:
            self.blips[icao] = {'msg': msg, 'timestamp': time.time(), 'count': 1}

        if not self.blips[icao]['msg'].decodeCPR_relative():
            self.blips[icao]['msg'].decodeCPR()

        if basic.ADSB.cfg_use_flight_db and msg['call_sign'] != "":
            self.flight_db.add(msg['call_sign'])

        self.lock.release()
        if self.cfg_verbose_logging:
            self.logger.info("{}".format(str(msg)))

    def _blip_exist(self, msg):
        return msg['ICAO24'] in self.blips

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
            if msg.get_downlink_format() == self.DF_ALL_CALL_REPLY_11:
                if msg.crc_ok:
                    self._blip_add(msg)
                else:
                    if basic.ADSB.crc_2_int(msg.crc_sum) < 80 and self._blip_exist(msg):
                        msg.crc_ok = True
                        self._blip_add(msg)
            elif msg.get_downlink_format() == self.DF_ADSB_MSG_17 and msg.crc_ok:
                self._blip_add(msg)
            elif msg.get_downlink_format() == self.DF_EXTENDED_SQUITTER_18 and msg.crc_ok:
                self._blip_add(msg)
            else:  # All other DF have CRC xor'ed with ICAO address
                if msg.crc_ok:
                    self._blip_add(msg)
                else:
                    # we use the crc_sum for ICAO, this is tested in the decode method of Squitter
                    msg['ICAO24'] = msg.crc_sum
                    msg.crc_ok = True if self._blip_exist(msg) else False
                    if msg.crc_ok:
                        self._blip_add(msg)

        self.logger.info("Radar stopping")

    def _die(self):
        self.logger.info("Radar dying")

        if basic.ADSB.cfg_use_flight_db:
            self.flight_db.dump()
            self.flight_timer.cancel()
        self.finished.set()
        self.blip_timer.cancel()
        self.stat_timer.cancel()
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


def run_Radar():
    print "Spots version {}".format(basic.ADSB.VERSION)

    sys.stderr = open("spots.err", 'w')
    logger = logging.getLogger('spots')
    logger.setLevel(logging.DEBUG)
    fh = logging.handlers.RotatingFileHandler(filename=basic.ADSB.cfg_log_file,
                                              mode='w',
                                              maxBytes=basic.ADSB.cfg_log_max_bytes,
                                              backupCount=basic.ADSB.cfg_log_backup_count)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - (%(threadName)-10s) - %(message)s')
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

    host = basic.ADSB.cfg_server_address
    port = basic.ADSB.cfg_server_port

    spots_server = server.SpotsServer((host, port), radar)
    spots_server.start()

    logger.info("Spots message server running, listening on {}:{}".format(host, port))

    tuner1090.read(radar.tuner_read)  # This is the main loop and main thread

    spots_server.die()


if __name__ == '__main__':
    run_Radar()
