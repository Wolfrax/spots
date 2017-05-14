# spots - dump1090 in Python

An implementation to detect and decode Mode-S messages modulated on 1090MHz.
The implementation is implemented fully in Python, tested on raspberry pi 2 model B hardware using an 
RTL-SDR USB dongle.

Focus is on using Python idioms and readability, not optimizations.
Other implementations in C are likely more efficient.

The implementation is multi-threaded:
* Tuner: sample the signal
* Squitter: decoded messages
* Radar: main application that displays messages
* Basic: fundamentals

It tries to be as complete and accurate as possible but with no guarantees of being correct.

The following message will be decoded:

* Short air-to-air surveillance (Downlink format: 0)
* Surveillance altitude reply (Downlink format: 4)
* Surveillande identity reply (Downlink format: 5)
* Long air-to-air surveillance (Downlink format: 16)
* ADS-B (Downlink format:17)
* Extended Squitter (Downlink format: 17)
* Comm BDS altitude reply (Downlink format: 20)
* Comm BDS identity reply (Downlink format: 21)

Messages decoded are displayed either in a serialised format on standard output
or in a tabular format depending on preference.

Some statistics is collected

## Dependencies

Spots uses [pyrtlsdr](https://github.com/roger-/pyrtlsdr) to read samples. Use the installation description to install
this.

pyrtlsdr is wrapper for rtlsdr library, so this needs to be installed.

See the following references:

* http://sdr.osmocom.org/trac/wiki/rtl-sdr
* http://zr6aic.blogspot.se/2013/02/setting-up-my-raspberry-pi-as-sdr-server.html

The following worked for me

    $ sudo apt-get update
    $ sudo apt-get install cmake
    $ sudo apt-get install libusb-1.0-0.dev
    $ git clone git://git.osmocom.org/rtl-sdr.git
    $ cd rtl-sdr/
    $ mkdir build
    $ cd build
    $ cmake ../
    $ make
    $ sudo make install
    $ sudo ldconfig

Edit the blacklist
 
    $ sudo nano /etc/modprobe.d/raspi-blacklist.conf

Add these lines

    blacklist dvb_usb_rtl28xxu
    blacklist rtl2832
    blacklist rtl2830

Finally

    $ sudo cp ../rtl-sdr.rules /etc/udev/rules.d/
    $ sudo shutdown -r 0


## References

As the implementation have no access to specifications the following implementations serves
as references for spots

* [dump1090 by antirez](https://github.com/antirez/dump1090), the original
* [dump1090 by Malcolm Robb](https://github.com/MalcolmRobb/dump1090), a fork of antirez original
* [dump1090 by flighaware](https://github.com/flightaware/dump1090), another forl
* [java adsb at OpenSky](https://github.com/openskynetwork/java-adsb), a java implementation

## Usage

Simply try

    $ python radar.py

## Configuration options

Configuration for spots is in `spots_config.json`. Follows json syntax with no error checks so be careful.

* verbose logging (true/false): writes messages to spots logfile
* check crc (true/false): whether to check crc (recommended) or not
* use metric (true/false): show values in metric system or not (altitude and velocity)
* apply bit error correction (true/false): whether to try to correct bit errors or not (CPU demanding if true)
* read from file (true/false): if true, read samples from a file rather than from the USB dongle
* file name (string): if "read from file" is true, this is the file to read from
* use text display (true/false): if true, show data in table format, if false show in serialised way
* max blip ttl (integer or float): how many seconds to keep an identified aircraft in the table display
* user latitude (float): your latitude position
* user longitude (float): and your longitude
* log file (string): The name of the log file
* log max bytes (integer): How many bytes to log before the log file is rotated
* log backup count (integer): How many roted log files to keep

## What's next?

There is probably inconsistencies, bugs, optimizations, documentation etc etc to make.
If you find something, let me know but be aware that this is a leisure thing for me.

Current directions are:

* decode more information from received messages
* do some more statistical collection
* add web server/client possibilities