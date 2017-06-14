import threading
import json
import time

__author__ = 'Wolfrax'

"""
basic implement fundamentals of spots, the class ADSB includes constants, pre-defined tables and configuration
options. Methods are:

    _data_2_long: converts samples into bits
    _apply_phase_correction: tries to correct when there is a time shift detected in the signal (CPU intensive)
    _alt_apply_phase_correction: similar to above but simpler
    _detect_adsb: scans samples for a valid preamble
    _hex_str_2_bin_str: conversion
    _alt_crc_func: calculates a crc sum using a lookup table
    _crc_func(: calculates a crc sum using the GENERATOR polynom
    crc: calls either _alt_crc_func or _crc_func, this function are called by other classes
    correct_biterror: tries to correct biterrors by flipping bits (CPU consuming)
    _preamble_signal_strength: estimates the signal strength of the preamble
    _check_phase: tries to estimates how much out of phase the sampling is
    _detect_preamble: tries to detect a preamble among the samples
    crc_2_int: conversion
    _bin_list_2_hex_str: conversion

Included is the RepeatTimer and Stats classes.
"""

with open("squitter.json", "r") as f:
    squitter_json = json.load(f)

with open("spots_config.json", "r") as f:
    config_json = json.load(f)


class ADSB:
    """
    This class defines fundamental constants and is not supposed to be instantiated
    """

    VERSION = "2.1"

    # basic constants
    MODES_SIGMIN = 0
    MODES_SIGMAX = 65535
    MODES_SIG_QUARTER = MODES_SIGMAX / 4

    MODES_PREAMBLE_US = 8  # microseconds
    PREAMBLE_SAMPLES = 2 * MODES_PREAMBLE_US
    MODES_PREAMBLE_SIZE = 2 * PREAMBLE_SAMPLES

    MODES_SHORT_MSG_BITS = 56
    MODES_SHORT_MSG_BYTES = MODES_SHORT_MSG_BITS / 8
    MODES_SHORT_MSG_SAMPLES = 2 * MODES_SHORT_MSG_BITS

    MODES_LONG_MSG_BITS = 2 * MODES_SHORT_MSG_BITS
    MODES_LONG_MSG_BYTES = MODES_LONG_MSG_BITS / 8
    MODES_LONG_MSG_SAMPLES = 2 * MODES_LONG_MSG_BITS

    SQUITTER_SHORT_MAX_SIZE = PREAMBLE_SAMPLES + MODES_SHORT_MSG_SAMPLES
    SQUITTER_LONG_MAX_SIZE = PREAMBLE_SAMPLES + MODES_LONG_MSG_SAMPLES

    MODES_ASYNC_BUF_NUMBER = 16

    MODES_DATA_LEN = MODES_ASYNC_BUF_NUMBER * 1024 * PREAMBLE_SAMPLES  # 256k
    MODES_FULL_LEN = MODES_PREAMBLE_US + MODES_LONG_MSG_BITS
    MODES_DATA_OFFSET = PREAMBLE_SAMPLES  # Where data starts after the preamble

    METER_PER_FOOT = 0.3048
    KPH_PER_KNOT = 1.852

    MAX_17_BITS = float(2**17)

    # Downlink formats
    DF_SHORT_AIR2AIR_SURVEILLANCE_0 = "0"
    DF_UNKNOWN_1 = "1"
    DF_UNKNOWN_2 = "2"
    DF_UNKNOWN_3 = "3"
    DF_SURVEILLANCE_ALTITUDE_REPLY_4 = "4"
    DF_SURVEILLANCE_IDENTITY_REPLY_5 = "5"
    DF_UNKNOWN_6 = "6"
    DF_UNKNOWN_7 = "7"
    DF_UNKNOWN_8 = "8"
    DF_UNKNOWN_9 = "9"
    DF_UNKNOWN_10 = "10"
    DF_ALL_CALL_REPLY_11 = "11"
    DF_UNKNOWN_12 = "12"
    DF_UNKNOWN_13 = "13"
    DF_UNKNOWN_14 = "14"
    DF_UNKNOWN_15 = "15"
    DF_LONG_AIR2AIR_SURVEILLANCE_16 = "16"
    DF_ADSB_MSG_17 = "17"
    DF_EXTENDED_SQUITTER_18 = "18"
    DF_MILITARY_EXTENDED_SQUITTER_19 = "19"
    DF_COMM_BDS_ALTITUDE_REPLY_20 = "20"
    DF_COMM_BDS_IDENTITY_REPLY_21 = "21"
    DF_MILITARY_USE_22 = "22"
    DF_UNKNOWN_23 = "23"
    DF_COMM_D_EXTENDED_LENGTH_MESSAGE_24 = "24"
    DF_UNKNOWN_25 = "25"
    DF_UNKNOWN_26 = "26"
    DF_UNKNOWN_27 = "27"
    DF_UNKNOWN_28 = "28"
    DF_UNKNOWN_29 = "29"
    DF_UNKNOWN_30 = "30"
    DF_UNKNOWN_31 = "31"
    DF_SSR_MODE_AC_REPLY_32 = "32"

    # Type codes
    TC_NO_INFO_0 = 0
    TC_ID_CAT_D_1 = 1
    TC_ID_CAT_C_2 = 2
    TC_ID_CAT_B_3 = 3
    TC_ID_CAT_A_4 = 4
    TC_SURFACE_POS_5 = 5
    TC_SURFACE_POS_6 = 6
    TC_SURFACE_POS_7 = 7
    TC_SURFACE_POS_8 = 8
    TC_AIRBORNE_POS_9 = 9  # Barometric
    TC_AIRBORNE_POS_10 = 10  # Barometric
    TC_AIRBORNE_POS_11 = 11  # Barometric
    TC_AIRBORNE_POS_12 = 12  # Barometric
    TC_AIRBORNE_POS_13 = 13  # Barometric
    TC_AIRBORNE_POS_14 = 14  # Barometric
    TC_AIRBORNE_POS_15 = 15  # Barometric
    TC_AIRBORNE_POS_16 = 16  # Barometric
    TC_AIRBORNE_POS_17 = 17  # Barometric
    TC_AIRBORNE_POS_18 = 18  # Baromtric
    TC_AIRBORNE_VELOCITY_19 = 19
    TC_AIRBORNE_POS_20 = 20  # GNSS
    TC_AIRBORNE_POS_21 = 21  # GNSS
    TC_AIRBORNE_POS_22 = 22  # GNSS
    TC_RESERVED_TEST_23 = 23
    TC_RESERVED_SURFACE_SYSTEM_STATUS_24 = 24
    TC_RESERVED_25 = 25
    TC_RESERVED_26 = 26
    TC_RESERVED_27 = 27
    TC_EXT_SQ_AIRCRFT_STATUS_28 = 28
    TC_TARGET_STATE_STATUS_29 = 29
    TC_NO_LONGER_USED_30 = 30
    TC_AIRCRAFT_OPERAIONAL_STATUS_31 = 31

    MODES_CHECKSUM_TABLE = (
        0x3935ea, 0x1c9af5, 0xf1b77e, 0x78dbbf, 0xc397db, 0x9e31e9, 0xb0e2f0, 0x587178,
        0x2c38bc, 0x161c5e, 0x0b0e2f, 0xfa7d13, 0x82c48d, 0xbe9842, 0x5f4c21, 0xd05c14,
        0x682e0a, 0x341705, 0xe5f186, 0x72f8c3, 0xc68665, 0x9cb936, 0x4e5c9b, 0xd8d449,
        0x939020, 0x49c810, 0x24e408, 0x127204, 0x093902, 0x049c81, 0xfdb444, 0x7eda22,
        0x3f6d11, 0xe04c8c, 0x702646, 0x381323, 0xe3f395, 0x8e03ce, 0x4701e7, 0xdc7af7,
        0x91c77f, 0xb719bb, 0xa476d9, 0xadc168, 0x56e0b4, 0x2b705a, 0x15b82d, 0xf52612,
        0x7a9309, 0xc2b380, 0x6159c0, 0x30ace0, 0x185670, 0x0c2b38, 0x06159c, 0x030ace,
        0x018567, 0xff38b7, 0x80665f, 0xbfc92b, 0xa01e91, 0xaff54c, 0x57faa6, 0x2bfd53,
        0xea04ad, 0x8af852, 0x457c29, 0xdd4410, 0x6ea208, 0x375104, 0x1ba882, 0x0dd441,
        0xf91024, 0x7c8812, 0x3e4409, 0xe0d800, 0x706c00, 0x383600, 0x1c1b00, 0x0e0d80,
        0x0706c0, 0x038360, 0x01c1b0, 0x00e0d8, 0x00706c, 0x003836, 0x001c1b, 0xfff409,
        0x000000, 0x000000, 0x000000, 0x000000, 0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000, 0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000, 0x000000, 0x000000, 0x000000, 0x000000)

    GENERATOR = "1111111111111010000001001"

    NL = (
        87.00000000, 86.53536998, 85.75541621, 84.89166191, 83.99173563, 83.07199445, 82.13956981, 81.19801349,
        80.24923213, 79.29428225, 78.33374083, 77.36789461, 76.39684391, 75.42056257, 74.43893416, 73.45177442,
        72.45884545, 71.45986473, 70.45451075, 69.44242631, 68.42322022, 67.39646774, 66.36171008, 65.31845310,
        64.26616523, 63.20427479, 62.13216659, 61.04917774, 59.95459277, 58.84763776, 57.72747354, 56.59318756,
        55.44378444, 54.27817472, 53.09516153, 51.89342469, 50.67150166, 49.42776439, 48.16039128, 46.86733252,
        45.54626723, 44.19454951, 42.80914012, 41.38651832, 39.92256684, 38.41241892, 36.85025108, 35.22899598,
        33.53993436, 31.77209708, 29.91135686, 27.93898710, 25.82924707, 23.54504487, 21.02939493, 18.18626357,
        14.82817437, 10.47047130, 0)

    squitter = squitter_json
    config = config_json

    # Configuration options
    cfg_check_phase = config["check phase"]
    cfg_use_metric = config["use metric"]
    cfg_apply_bit_err_correction = config["apply bit err correction"]
    cfg_run_as_daemon = config["run as daemon"]
    cfg_read_from_file = config["read from file"]
    cfg_file_name = config["file name"]
    cfg_use_text_display = config["use text display"]
    cfg_max_blip_ttl = config["max blip ttl"]
    cfg_verbose_logging = config["verbose logging"]
    cfg_check_crc = config["check crc"]
    cfg_latitude = config["user latitude"]
    cfg_longitude = config["user longitude"]
    cfg_log_file = config["log file"]
    cfg_log_max_bytes = config["log max bytes"]
    cfg_log_backup_count = config["log backup count"]
    cfg_server_address = config["spots server address"]
    cfg_server_port = config["spots server port"]

    def __init__(self):
        pass

    def _data_to_long(self, msg):
        """
        Convert samples into bits assuming manchester coding (high to low is 1, low to high is 0)
        """
        bits = 0
        for ind in range(self.MODES_DATA_OFFSET, len(msg), 2):
            bits = (bits << 1) | (1 if msg[ind] > msg[ind + 1] else 0)
        return bits

    def _apply_phase_correction(self, msg):
        """
        This algorithm builds on the fact that a phase error have been detected.
        Bits after the pre-amble (bits 16 and forward with first pre-amble bit at position 0) is encoded using ASK/OOK
        using Manchester coding. 
    
        This means that a '1' is represented by 2 samples where the first sample is higher than the last sample.
        A '0' is represented by the first sample being lower than the second sample
    
        high    *                    !   high    *
                *      represents 1  !           *    represents 0
        low     * *                  !    low  * *
        sample  1 2                  ! sample  1 2
    
        Thus a sequence of equal bits "1111" is represented as
    
        bit      1   1   1   1
        high    *   *   *   *
                *   *   *   *
        low     * * * * * * * *
        sample  1 2 3 4 5 6 7 8
    
        If the sampling is out of phase the low sample (positions 2 4 6 8) are interfered by the high samples, 
        (positions 1 3 5 7) either if the out of phase is left or right shifted. we might end up with
    
        bit      1   1   1   1
        high    *       *   *
                * * * * * * * *
        low     * * * * * * * *
        sample  1 2 3 4 5 6 7 8
    
        Similar to a sequence of zero's.
        Thus we apply a simple transformation here by increasing the following sample (msg[ind+2]) 
        with 5/4 if the previous samples (msg[ind] and msg[ind+1]) was a '1' (msg[ind] > msg[ind+1]). 
        We decrease the following sample (msg[ind+2]) with 4/5 if the previous samples (msg[ind] and msg[ind+1]) 
        was a '0' (msg[ind] < msg[ind+1])
    
        This will increase the possibility to correctly detect a sequence of equal bits ('0000' or '1111') even if the
        sampling is out of phase. 
        When there is an alternating sequence of bits, e.g. '01', this is represented as 'low high high low' if we are
        out of phase the middle high samples will only be increased due to the phase error but still detected as '01'.
        If the sequence is '10' the samples are 'high low low high' and the middle low samples are increased but 
        probably below the level of high samples so still detected as '10'.
         """
        for ind in range(self.MODES_DATA_OFFSET, len(msg) - 2, 2):
            if msg[ind] > msg[ind + 1]:  # One
                msg[ind + 2] = (msg[ind + 2] * 5) / 4
            else:  # Zero
                msg[ind + 2] = (msg[ind + 2] * 4) / 5

    def _alt_apply_phase_correction(self, msg):
        """
        NB! msg index 0 is one sample before first preamble sample (which starts at 1)
    
        The preamble should ideally look like this
    
        high      *   *         *   *
                  *   *         *   *
        low     * * * * * * * * * * *  *  *  *  *  *
        bit nr  0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
    
        Preamble detected starts at bit 1
    
        This function decides whether we are sampling early or late,
        and by approximately how much, by looking at the energy in
        preamble bits before and after the expected pulse locations.
    
        It then deals with one sample pair at a time, comparing samples
        to make a decision about the bit value. Based on this decision it
        modifies the sample value of the *adjacent* sample which will
        contain some of the energy from the bit we just inspected.
    
        """

        # use preamble samples 0,7 for early detection (bit 1/8 arrived a little early, our sample period starts
        # after the bit phase so we include some of the next bit)
        #
        # use preamble samples 4,11 for late detection (bit 3/10 arrived a little late, our sample period starts
        # before the bit phase so we include some of the last bit)

        on_time = msg[1] + msg[3] + msg[8] + msg[10]
        early = (msg[0] + msg[7]) * 2
        late = (msg[4] + msg[11]) * 2

        if (early + on_time) == 0 or (late + on_time) == 0:
            return
        if early > late:
            # Our sample period starts late and so includes some of the next bit.

            scale_up = self.MODES_SIG_QUARTER + self.MODES_SIG_QUARTER * early / (early + on_time)
            scale_down = self.MODES_SIG_QUARTER - self.MODES_SIG_QUARTER * early / (early + on_time)

            # trailing bits are 0; final data sample will be a bit low.
            scale = msg[self.PREAMBLE_SAMPLES + self.MODES_LONG_MSG_BITS * 2 - 1] * scale_up / self.MODES_SIG_QUARTER
            msg[self.PREAMBLE_SAMPLES + self.MODES_LONG_MSG_BITS * 2 - 1] = \
                self.MODES_SIGMAX if (scale > self.MODES_SIGMAX) else scale
            for ind in range(self.PREAMBLE_SAMPLES + self.MODES_LONG_MSG_BITS * 2 - 2, self.PREAMBLE_SAMPLES, -2):
                if msg[ind] > msg[ind + 1]:
                    # x [1 0] y
                    # x overlapped with the "1" bit and is slightly high
                    scale = msg[ind - 1] * scale_down / self.MODES_SIG_QUARTER
                    msg[ind - 1] = self.MODES_SIGMAX if (scale > self.MODES_SIGMAX) else scale
                else:
                    # x [0 1] y
                    # x overlapped with the "0" bit and is slightly low
                    scale = msg[ind - 1] * scale_up / self.MODES_SIG_QUARTER
                    msg[ind - 1] = self.MODES_SIGMAX if (scale > self.MODES_SIGMAX) else scale
        else:
            # Our sample period starts early and so includes some of the previous bit.

            scale_up = self.MODES_SIG_QUARTER + self.MODES_SIG_QUARTER * late / (late + on_time)
            scale_down = self.MODES_SIG_QUARTER - self.MODES_SIG_QUARTER * late / (late + on_time)

            # leading bits are 0; first data sample will be a bit low.
            scale = msg[self.PREAMBLE_SAMPLES] * scale_up / self.MODES_SIG_QUARTER
            msg[self.PREAMBLE_SAMPLES] = self.MODES_SIGMAX if (scale > self.MODES_SIGMAX) else scale
            for ind in range(self.PREAMBLE_SAMPLES, self.PREAMBLE_SAMPLES + self.MODES_LONG_MSG_BITS * 2 - 2, 2):
                if msg[ind] > msg[ind + 1]:
                    # x [1 0] y
                    # y overlapped with the "0" bit and is slightly low
                    scale = msg[ind + 2] * scale_up / self.MODES_SIG_QUARTER
                    msg[ind + 2] = self.MODES_SIGMAX if (scale > self.MODES_SIGMAX) else scale
                else:
                    # x [0 1] y
                    # y overlapped with the "1" bit and is slightly high
                    scale = msg[ind + 2] * scale_down / self.MODES_SIG_QUARTER
                    msg[ind + 2] = self.MODES_SIGMAX if (scale > self.MODES_SIGMAX) else scale

    def _detect_adsb(self, sig):
        """
            The preamble should ideally look like this
    
        high      *   *         *   *     
                  *   *         *   *     
        low       * * * * * * * * * * *  *  *  *  * 
        bit nr    0 1 2 3 4 5 6 7 8 9 10 11 12 13 14
    
        :param sig: 
        :return: 
        """
        arr = []
        max_length = len(sig) - self.SQUITTER_LONG_MAX_SIZE
        ind = 0
        while ind < max_length:
            if self._detect_preamble(sig, ind):
                sig_strength = self._preamble_signal_strength(sig[ind: ind + self.PREAMBLE_SAMPLES])
                arr.append([sig_strength, sig[ind:ind + self.SQUITTER_LONG_MAX_SIZE]])

                # Determine if we have found a long or short squitter and increment ind accordingly
                msg = self._data_to_long(sig[ind:ind + self.SQUITTER_LONG_MAX_SIZE])
                downlink_format = (int(hex(msg)[2:4], base=16) & 0xF8) >> 3
                if downlink_format & 0x10:
                    ind += self.SQUITTER_LONG_MAX_SIZE
                else:
                    ind += self.SQUITTER_SHORT_MAX_SIZE
                continue
            else:
                if ind > 0 and self.cfg_check_phase:
                    phase_err = self._check_phase(sig[ind - 1:ind + 11])  # Check phase on preamble
                    if phase_err != 0:
                        # we are out of phase left (-1) or right (1), phase correct on reminder of sig, skip preamble
                        # self._alt_apply_phase_correction(sig[ind:ind + self.SQUITTER_LONG_MAX_SIZE])
                        self._apply_phase_correction(sig[ind:ind + self.SQUITTER_LONG_MAX_SIZE])
                        if self._detect_preamble(sig, ind):
                            sig_strength = self._preamble_signal_strength(sig[ind: ind + self.PREAMBLE_SAMPLES])
                            arr.append([sig_strength, sig[ind:ind + self.SQUITTER_LONG_MAX_SIZE]])
            ind += 1
        # NB _data_to_long transformation will skip the preamble samples
        return [[arr[ind][0], self._data_to_long(arr[ind][1])] for ind in range(len(arr))]

    def _hex_str_2_bin_str(self, hexstr):
        """
        Convert a hexdecimal string to binary string, with zero fillings. 
        If the hex string have a trailing 'L' (Long) it is removed
        """
        hexstr = hexstr.rstrip('L').lstrip('0x')
        # We have a long (112 bits, 14 bytes message => 28 hex string)
        # Pad hexstring with zero's (to the left) to ensure right length
        if len(hexstr) > (2 * self.MODES_SHORT_MSG_BYTES):
            hexstr = hexstr.zfill(self.MODES_LONG_MSG_BYTES * 2)
        else:
            hexstr = hexstr.zfill(self.MODES_SHORT_MSG_BYTES * 2)

        return bin(int(hexstr, base=16))[2:].zfill(len(hexstr) * 4)

    def _alt_crc_func(self, msg):
        """    
        Mode-S Cyclic Redundancy Check
        Detect if bit error occurs in the Mode-S message
        Args:
            msg (string): 28 bytes hexadecimal message string 
        Returns:
            hex string: message checksum
        """
        if msg == '0':
            return msg

        bin_list = list(self._hex_str_2_bin_str(msg))

        crc_val = 0
        offset = 0 if len(bin_list) == self.MODES_LONG_MSG_BITS else self.MODES_SHORT_MSG_BITS

        for i in range(len(bin_list) - 24):
            if bin_list[i] == '1':
                crc_val ^= self.MODES_CHECKSUM_TABLE[i + offset]

        check_sum = int(self._bin_list_2_hex_str(bin_list[-24:]), base=16)
        result = (crc_val ^ check_sum) & 0x00FFFFFF
        return hex(result)[2:]

    def _crc_func(self, msg):
        """
        Mode-S Cyclic Redundancy Check
        Detect if bit error occurs in the Mode-S message
        """
        # the polynominal generator code for crc_sum

        if msg == '0':
            return msg

        bin_list = list(self._hex_str_2_bin_str(msg))

        # msgbin[-24:] = ['0'] * 24 if encode else None

        # loop all bits, except last 24 parity bits
        for i in range(len(bin_list) - 24):
            # if 1, perform modulo 2 multiplication,
            if bin_list[i] == '1':
                for j in range(len(self.GENERATOR)):
                    # modulo 2 multiplication = XOR
                    bin_list[i + j] = str((int(bin_list[i + j]) ^ int(self.GENERATOR[j])))

        # last 24 bits
        return self._bin_list_2_hex_str(bin_list[-24:])

    def crc(self, msg):
        """
        Calls the crc function in use, either _alt_crc_func or _crc_func
        """
        return self._alt_crc_func(msg)

    def correct_biterror(self, msg, bits=1):
        """
        Tries to correct bit errors by flipping one bit at a time in msg and calculate a new crc_sum.
        If the new crc_sum is zero we have corrected the error and return the corrected string
    
        Default is to do this on 1 bit (bits defaults to 1), if bits is 2 try to do it on 2 bits instead.
        If bits equals 2 this is a VERY time consuming process and should not be used.
        :param msg: The message to be checked, hex string
        :param bits: No of bits to be corrected
        :return: a corrected message or None
        """
        if bits != 1 and bits != 2:
            return None

        bin_str = self._hex_str_2_bin_str(msg)
        bin_list = list(bin_str)
        # msgbin = list(hex_str_2_bin_str(msg))

        for i in range(5, len(bin_list)):
            bin_list[i] = '0' if bin_list[i] == '1' else '1'  # Flip bit
            if bits == 1:
                res = self._bin_list_2_hex_str(bin_list)
                if self.crc_2_int(self.crc(res)) == 0:  # We found that crc_sum is Ok with this bit flip
                    return int(res)  # Return the corrected message
            else:
                for j in range(i + 1, len(bin_list)):
                    bin_list[j] = '0' if bin_list[j] == '1' else '1'  # Flip bit
                    res = self._bin_list_2_hex_str(bin_list)
                    if self.crc_2_int(self.crc(res)) == 0:
                        return int(res)  # Return the corrected message
                    bin_list[j] = '0' if bin_list[j] == '1' else '1'  # Flip bit back
            bin_list[i] = '0' if bin_list[i] == '1' else '1'  # Flip bit back
        return None

    def _preamble_signal_strength(self, sig):
        """
        Calculate the signal strength from the min and max of the preamble samples normalized on range, expressed in %
        """
        return round(((max(sig[0:14]) - min(sig[0:14])) / float(self.MODES_SIGMAX)) * 100, 1)

    @staticmethod
    def _check_phase(preamble):
        """
        This procedure checks the relation of high amplitudes vs low amplitudes
        The preamble should ideally look like this
    
        high      *   *         *   *
                  *   *         *   *
        low     * * * * * * * * * * *  *
        bit nr  0 1 2 3 4 5 6 7 8 9 10 11
    
        Preamble detected starts at bit 1
    
        Below we compare the amplitude of low bit vs high bits
        - if bit 4 amplitude is larger than 1/3 of bit 3 we have a shift right of the signal
        - if bit 11 amplitude is larger than 1/3 of of bit 10 we have a right shift of the signal
        - if bit 7 amplitude is larger than 1/3 of bit 8 we have a left shift of the signal
        - if bit 0 amplitude is larger than 1/3 of bit 1 we have a left shift of the signal
        - if none occur we are in phase
        """
        if preamble[4] > preamble[3] / 3:  # low bit is larger than 1/3 of high bit
            return preamble[4]
        elif preamble[11] > preamble[10] / 3:  # low bit is larger than 1/3 of high bit
            return preamble[11]
        elif preamble[7] > preamble[8] / 3:
            return preamble[7]
        elif preamble[0] > preamble[1] / 3:  # NB, dump1090 uses bit 2 here instead of 1, bug?
            return preamble[0]
        else:
            return 0

    @staticmethod
    def _detect_preamble(sig, ind):
        """
        Detects a preamble from sig
        
        The preamble should ideally look like this
    
        high      *   *         *   *     
                  *   *         *   *     
        low       * * * * * * * * * * *  *  *  *  * 
        bit nr    0 1 2 3 4 5 6 7 8 9 10 11 12 13 14
        """

        if sig[ind + 0] > sig[ind + 1] \
                and sig[ind + 1] < sig[ind + 2] \
                and sig[ind + 2] > sig[ind + 3] \
                and sig[ind + 3] < sig[ind + 0] \
                and sig[ind + 4] < sig[ind + 0] \
                and sig[ind + 5] < sig[ind + 0] \
                and sig[ind + 6] < sig[ind + 0] \
                and sig[ind + 7] > sig[ind + 8] \
                and sig[ind + 8] < sig[ind + 9] \
                and sig[ind + 9] > sig[ind + 6]:

            high = (sig[ind + 0] + sig[ind + 2] + sig[ind + 7] + sig[ind + 9]) / 6
            if sig[ind + 4] < high \
                    and sig[ind + 5] < high \
                    and sig[ind + 11] < high \
                    and sig[ind + 12] < high \
                    and sig[ind + 13] < high \
                    and sig[ind + 14] < high:
                return True
        return False

    @staticmethod
    def crc_2_int(crc_sum):
        """
        Convert the crc_sum hex-string to integer
        """
        return int(crc_sum.rstrip('L'), base=16)

    @staticmethod
    def _bin_list_2_hex_str(bin_list):
        """
        Convert a list of binaries to a hexadecimal string
        """
        return hex(int(''.join(bin_list), 2))[2:]


class RepeatTimer(threading.Thread):
    def __init__(self, interval, func, name):
        threading.Thread.__init__(self, name=name)
        self.interval = interval
        self.function = func
        self.finished = threading.Event()
        self.daemon = True

    def run(self):
        while not self.finished.is_set():
            self.finished.wait(self.interval)
            if not self.finished.is_set():
                self.function()

    def cancel(self):
        self.finished.set()


class Stats:
    """
    Class for collecting some statistics on messages
    """
    data = {'spots_version': "",
            'start_time': 0,
            'start_time_string': "",
            'valid_preambles': 0,
            'valid_crc': 0,
            'not_valid_crc': 0,
            'df_0': 0,
            'df_1': 0,
            'df_2': 0,
            'df_3': 0,
            'df_4': 0,
            'df_5': 0,
            'df_6': 0,
            'df_7': 0,
            'df_8': 0,
            'df_9': 0,
            'df_10': 0,
            'df_11': 0,
            'df_12': 0,
            'df_13': 0,
            'df_14': 0,
            'df_15': 0,
            'df_16': 0,
            'df_17': 0,
            'df_18': 0,
            'df_19': 0,
            'df_20': 0,
            'df_21': 0,
            'df_22': 0,
            'df_23': 0,
            'df_24': 0,
            'df_25': 0,
            'df_26': 0,
            'df_27': 0,
            'df_28': 0,
            'df_29': 0,
            'df_30': 0,
            'df_31': 0,
            'df_total': 0
            }

    def __init__(self):
        self['spots_version'] = ADSB.VERSION
        self['start_time'] = time.time()
        self['start_time_string'] = time.ctime(self['start_time'])
        pass

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getitem__(self, item):
        return self.data[item]

    def __str__(self):
        st = "\n"
        st += "Preambles:{}\n".format(self['valid_preambles'])
        st += "Valid CRC:{}\n".format(self['valid_crc'])
        st += "Non valid CRC:{}\n".format(self['not_valid_crc'])
        st += "Decoded messages: "
        st += "DF0: {} ".format(self['df_0'])
        st += "DF4: {} ".format(self['df_4'])
        st += "DF5: {} ".format(self['df_5'])
        st += "DF11: {} ".format(self['df_11'])
        st += "DF16: {} ".format(self['df_16'])
        st += "DF17: {} ".format(self['df_17'])
        st += "DF18: {} ".format(self['df_18'])
        st += "DF20: {} ".format(self['df_20'])
        st += "DF21: {} ".format(self['df_21'])
        st += "DF Total: {} ".format(self['df_total'])

        return st


statistics = Stats()
