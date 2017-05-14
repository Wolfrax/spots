import basic
import math

"""
Implements the Squitter class which represents decoded messages.
"""


def callsign(cs):
    char_set = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######'

    csbin = bin(int(cs, 16))[2:].zfill(len(cs) * 4)[40:88]
    sign = ""
    sign += char_set[int(csbin[00:06], 2)]
    sign += char_set[int(csbin[06:12], 2)]
    sign += char_set[int(csbin[12:18], 2)]
    sign += char_set[int(csbin[18:24], 2)]
    sign += char_set[int(csbin[24:30], 2)]
    sign += char_set[int(csbin[30:36], 2)]
    sign += char_set[int(csbin[36:42], 2)]
    sign += char_set[int(csbin[42:48], 2)]
    return sign.translate(None, ''.join(['_', '#']))


def parse_id13(field):
    hex_gillham = 0

    if field & 0x1000:
        hex_gillham |= 0x0010  # Bit 12 = C1
    if field & 0x0800:
        hex_gillham |= 0x1000  # Bit 11 = A1
    if field & 0x0400:
        hex_gillham |= 0x0020  # Bit 10 = C2
    if field & 0x0200:
        hex_gillham |= 0x2000  # Bit 9 = A2
    if field & 0x0100:
        hex_gillham |= 0x0040  # Bit 8 = C4
    if field & 0x0080:
        hex_gillham |= 0x4000  # Bit 7 = A4
    if field & 0x0020:
        hex_gillham |= 0x0100  # Bit 5 = B1
    if field & 0x0010:
        hex_gillham |= 0x0001  # Bit 4 = D1 or Q
    if field & 0x0008:
        hex_gillham |= 0x0200  # Bit 3 = B2
    if field & 0x0004:
        hex_gillham |= 0x0002  # Bit 2 = D2
    if field & 0x0002:
        hex_gillham |= 0x0400  # Bit 1 = B4
    if field & 0x0001:
        hex_gillham |= 0x0004  # Bit 0 = D4

    return hex_gillham


def ModeA_2_ModeC(ModeA):
    # Input format is: 00:A4:A2:A1:00:B4:B2:B1:00:C4:C2:C1:00:D4:D2:D1
    five_hundreds = one_hundreds = 0

    if ((ModeA & 0xFFFF888B) or  # D1 set is illegal.D2 set is > 62700ft which is unlikely
            ((ModeA & 0x000000F0) == 0)):  # C1, , C4 cannot be Zero
        return -9999

    if ModeA & 0x0010:
        one_hundreds ^= 0x007  # C1
    if ModeA & 0x0020:
        one_hundreds ^= 0x003  # C2
    if ModeA & 0x0040:
        one_hundreds ^= 0x001  # C4

    # Remove 7s from one_hundreds (Make 7->5, snd 5->7).
    if (one_hundreds & 5) == 5:
        one_hundreds ^= 2

    # Check for invalid codes, only 1 to 5 are valid
    if one_hundreds > 5:
        return -9999

    # if (ModeA & 0x0001) {five_hundreds ^= 0x1FF;} // D1 never used for altitude
    if ModeA & 0x0002:
        five_hundreds ^= 0x0FF  # D2
    if ModeA & 0x0004:
        five_hundreds ^= 0x07F  # D4

    if ModeA & 0x1000:
        five_hundreds ^= 0x03F  # A1
    if ModeA & 0x2000:
        five_hundreds ^= 0x01F  # A2
    if ModeA & 0x4000:
        five_hundreds ^= 0x00F  # A4

    if ModeA & 0x0100:
        five_hundreds ^= 0x007  # B1
    if ModeA & 0x0200:
        five_hundreds ^= 0x003  # B2
    if ModeA & 0x0400:
        five_hundreds ^= 0x001  # B4

    # Correct order of one_hundreds.
    if five_hundreds & 1:
        one_hundreds = 6 - one_hundreds

    return (five_hundreds * 5) + one_hundreds - 13


def parse_ac13(field):
    """
    Parse the 13 bit AC altitude field
    :param field: to be decoded
    :return: altitude in feet
    """
    m_bit = field & 0x0040  # set = meters, clear = feet
    q_bit = field & 0x0010  # set = 25 ft encoding, clear = Gillham Mode C encoding

    if not m_bit:  # feet
        if q_bit:
            # n is the 11 bit integer resulting from the removal of bit Q and M
            n = ((field & 0x1F80) >> 2) | ((field & 0x0020) >> 1) | (field & 0x000F)
            # The final altitude is resulting number multiplied by 25, minus 1000
            return (n * 25) - 1000
        else:
            # n is an 11 bit Gillham coded altitude
            n = ModeA_2_ModeC(parse_id13(field))
            n = 0 if n < -12 else 100 * n
            return n
    else:  # meter
        return 0
        # TODO: Implement altitude when meter unit is selected


def parse_ac12(field):
    q_bit = field & 0x10  # Bit 48 = Q

    if q_bit != 0:
        # N is the 11 bit integer resulting from the removal of bit Q at bit 4
        n = ((field & 0x0FE0) >> 1) | (field & 0x000F)
        # The final altitude is the resulting number multiplied by 25, minus 1000.
        return (n * 25) - 1000
    else:
        # Make N a 13 bit Gillham coded altitude by inserting M=0 at bit 6
        n = ((field & 0x0FC0) << 1) | (field & 0x003F)
        n = ModeA_2_ModeC(parse_id13(n))
        return 0 if n < -12 else 100 * n


def parse_movement(movement):
    # Note : movement codes 0,125,126,127 are all invalid, but they are
    #        trapped for before this function is called.

    if movement > 123:
        gspeed = 199  # > 175kt
    elif movement > 108:
        gspeed = ((movement - 108) * 5) + 100
    elif movement > 93:
        gspeed = ((movement - 93) * 2) + 70
    elif movement > 38:
        gspeed = (movement - 38) + 15
    elif movement > 12:
        gspeed = ((movement - 11) >> 1) + 2
    elif movement > 8:
        gspeed = ((movement - 6) >> 2) + 1
    else:
        gspeed = 0

    return gspeed


def CPR_NL(lat):
    """
    Return index from pre-computed table
    :param lat: 
    :return: 
    """
    lat = abs(lat)
    if lat >= max(basic.ADSB.NL):
        return 1
    elif lat <= min(basic.ADSB.NL):
        return len(basic.ADSB.NL) + 1
    else:
        return basic.ADSB.NL.index(max(filter(lambda x: x < lat, basic.ADSB.NL))) + 1


def is_CPR(msg):
    return msg.is_CPR_msg


def is_odd_CPR(msg):
    return msg.odd


def decodeCPR(odd_msg, even_msg):
    # Basic algorithm: http://www.lll.lu/~edward/edward/adsb/DecodingADSBposition.html
    air_dlat_0 = 360 / 60.0
    air_dlat_1 = 360 / 59.0
    lat0 = even_msg.raw_latitude
    lat1 = odd_msg.raw_latitude
    lon0 = even_msg.raw_longitude
    lon1 = odd_msg.raw_longitude

    j = int(math.floor(((59 * lat0 - 60 * lat1) / 131072.0) + 0.5))

    rlat0 = air_dlat_0 * (j % 60 + lat0 / 131072.0)
    rlat1 = air_dlat_1 * (j % 59 + lat1 / 131072.0)

    # Adjust if we are on southern hemisphere by substracting 360 from latitude
    if rlat0 >= 270:
        rlat0 -= 360
    if rlat1 >= 270:
        rlat1 -= 360

    if rlat0 < -90 or rlat0 > 90 or rlat1 < -90 or rlat1 > 90:
        return None
    if CPR_NL(rlat0) != CPR_NL(rlat1):
        return None

    ni = max(CPR_NL(rlat1) - 1, 1)
    m = int(math.floor((((lon0 * (CPR_NL(rlat1) - 1)) - (lon1 * CPR_NL(rlat1))) / 131072.0) + 0.5))
    longitude = (360.0 / ni) * ((m % ni) + lon1 / 131072.0)
    latitude = rlat1

    if longitude > 180:
        longitude -= 360

    return {'latitude': latitude, 'longitude': longitude}


def decodeCPR_relative(odd_msg, even_msg):
    air_dlat_1 = 360 / 59.0

    if odd_msg.latitude != 0:
        latr = odd_msg.latitude
    elif even_msg.latitude != 0:
        latr = even_msg.latitude
    else:
        latr = odd_msg.cfg_latitude

    if odd_msg.longitude != 0:
        longr = odd_msg.longitude
    elif even_msg.latitude != 0:
        longr = even_msg.longitude
    else:
        longr = odd_msg.longitude

    tmp1 = math.floor(latr / air_dlat_1)
    tmp2 = (int(latr) % int(air_dlat_1))
    j = int(tmp1 + math.trunc(0.5 + tmp2 / air_dlat_1 - odd_msg.raw_latitude / 131072.0))
    rlat = air_dlat_1 * (j + odd_msg.raw_latitude / 131072.0)
    if rlat >= 270:
        rlat -= 360

    if rlat < -90 or rlat > 90:
        return None

    if abs(rlat - latr) > (air_dlat_1 / 2):
        return None

    air_dlon = 360 / max(CPR_NL(rlat) - 1, 1)
    m = int(math.floor(longr / air_dlon)
            + math.trunc(0.5 + (int(longr) % int(air_dlon)) / air_dlon - odd_msg.raw_longitude / 131072.0))
    rlon = air_dlon * (m + odd_msg.raw_longitude / 131072.0)
    if rlon > 180:
        rlon -= 360

    return {'latitude': rlat, 'longitude': rlon}


class Squitter(basic.ADSB):
    def __init__(self):
        basic.ADSB.__init__(self)

        # This is the Squitter object definition and initialization
        self.signal_strength = 0
        self.msg = 0
        self.no_of_bits = 0
        self.downlink_format = 0
        self.capability = 0
        self.ICAO24 = 0
        self.type_code = 0
        self.emitter_category = 0
        self.parity = 0
        self.crc_sum = "0"
        self.crc_ok = False
        self.Squawk = 0
        self.altitude = 0
        self.call_sign = ""
        self.vertical_rate = 0
        self.ew_velocity = 0
        self.ns_velocity = 0
        self.velocity = 0
        self.heading = 0
        self.flight_status = 0
        self.latitude = 0
        self.longitude = 0
        self.raw_latitude = 0
        self.raw_longitude = 0
        self.on_ground = False
        self.odd = False
        self.is_CPR_msg = False

    def __str__(self):
        st = ""
        st += "* {}\n".format(hex(self.msg)[2:-1])
        st += "{} ".format(hex(self.parity)[2:-1])
        st += "CRC: {} ({}) ".format(self.crc_sum, "ok" if self.crc_ok else "not ok")
        st += "ICAO: {} ".format(self.ICAO24)
        st += "DF - {} ".format(self.squitter["downlink format"][self.downlink_format])
        st += "TC - {} ".format(self.squitter["type code"][self.type_code])

        if self.altitude > 0:
            st += "{}ft ".format(self.altitude)
        if self.call_sign != "":
            st += "{} ".format(self.call_sign)
        if self.Squawk != 0:
            st += "Squawk: {:=04X} ".format(self.Squawk)
        if self.longitude != 0:
            st += "long: {0:.3f} ".format(self.longitude)
        if self.latitude != 0:
            st += "lat: {0:.3f} ".format(self.latitude)
        if self.vertical_rate != 0:
            st += "vrate: {} ".format(self.vertical_rate)
        if self.velocity != 0:
            st += "vel: {} ".format(self.velocity)
        if self.heading != 0:
            st += "head: {} ".format(self.heading)
        if self.flight_status != 0:
            st += "fs: {} {} ".format(self.flight_status, self.squitter["flight status"][self.flight_status])
        if self.signal_strength != 0:
            st += "sig: {}% ".format(self.signal_strength)

        return st

    def is_odd_CPR(self):
        return self.odd

    def is_CPR(self):
        return self.is_CPR_msg

    def add_lat_long(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude

    def _get_msg_byte(self, byte_nr):
        return (self.msg >> (self.no_of_bits - (byte_nr + 1) * 8)) & 0xFF

    def parse(self, obj):
        """
        Parse the message into the object
        """

        # The object consists of 2 parts: [signal_strength, msg]
        self.signal_strength = obj[0]
        msg = obj[1]

        # Top 5 bits is DF
        self.downlink_format = (int(hex(msg)[2:4], base=16) & 0xF8) >> 3

        # Most significant bit indicates length
        if self.downlink_format & 0x10:
            self.msg = msg
            self.no_of_bits = self.MODES_LONG_MSG_BITS
        else:
            self.msg = msg >> self.MODES_SHORT_MSG_BITS
            self.no_of_bits = self.MODES_SHORT_MSG_BITS

        if self.msg == 0:
            return

        if self.cfg_check_crc:
            self.crc_sum = self.crc(hex(self.msg))  # crc_sum is computed on a hexidecimal string
            self.crc_ok = basic.ADSB.crc_2_int(self.crc_sum) == 0
            if self.crc_ok:
                basic.statistics.valid_crc += 1
            else:
                basic.statistics.not_valid_crc += 1
        else:
            # Skip crc check, discouraged
            self.crc_sum = 0
            self.crc_ok = True

        if not self.crc_ok and self.cfg_apply_bit_err_correction:  # Apply bit error correction
            corrected_msg = self.correct_biterror(hex(self.msg), bits=1)
            if corrected_msg is not None:
                self.crc_ok = True
                self.msg = corrected_msg
                if self.crc_ok:
                    basic.statistics.valid_crc += 1
                else:
                    basic.statistics.not_valid_crc += 1

    def _get_vertical_rate(self):
        vertical_rate = ((self._get_msg_byte(8) & 0x07) << 6) | (self._get_msg_byte(9) >> 2)
        if vertical_rate != 0:
            vertical_rate -= 1
            if self._get_msg_byte(8) & 0x08:
                vertical_rate = 0 - vertical_rate
            vertical_rate = vertical_rate * 64
            if self.cfg_use_metric:
                return self.METER_PER_FOOT * vertical_rate if self.cfg_use_metric else vertical_rate

    def _get_altitude(self):
        ac_12 = ((self._get_msg_byte(5) << 4) | (self._get_msg_byte(6) >> 4)) & 0x0FFF
        if ac_12 != 0:
            altitude = parse_ac12(ac_12)
            return self.METER_PER_FOOT * altitude if self.cfg_use_metric else altitude
        else:
            return 0

    def _get_velocity(self):
        movement = ((self._get_msg_byte(4) << 4) | (self._get_msg_byte(5) >> 4)) & 0x007F
        if 0 < movement < 125:
            velocity = parse_movement(movement)
            return self.KPH_PER_KNOT * velocity if self.cfg_use_metric else velocity
        else:
            return 0

    def _get_heading(self):
        if self._get_msg_byte(5) & 0x08:
            return ((((self._get_msg_byte(5) << 4) | (self._get_msg_byte(6) >> 4)) & 0x007F) * 45) >> 4
        else:
            return 0

    def _get_identity(self):
        id_13 = ((self._get_msg_byte(2) << 8) | (self._get_msg_byte(3))) & 0x1FFF
        return parse_id13(id_13) if id_13 != 0 else 0

    def decode_ADSB_msg(self):
        if self.type_code == self.TC_TARGET_STATE_STATUS_29:
            sub_type = (self._get_msg_byte(4) & 0x06) >> 1
        else:
            sub_type = self._get_msg_byte(4) & 0x07

        if self.TC_ID_CAT_D_1 <= self.type_code <= self.TC_ID_CAT_A_4:
            self.call_sign = callsign(hex(self.msg)[2:-1])
        elif self.type_code == self.TC_AIRBORNE_VELOCITY_19:
            if 1 <= sub_type <= 4:
                self.vertical_rate = self._get_vertical_rate()
            if 1 <= sub_type <= 2:
                east_west_raw = ((self._get_msg_byte(5) & 0x03) << 8) | self._get_msg_byte(6)
                north_south_raw = ((self._get_msg_byte(7) & 0x7F) << 3) | (self._get_msg_byte(8) >> 5)
                ew_velocity = east_west_raw - 1
                ns_velocity = north_south_raw - 1

                if sub_type == 2:
                    ew_velocity <<= 2
                    ns_velocity <<= 2

                if east_west_raw != 0:
                    if self._get_msg_byte(5) & 0x04:
                        ew_velocity = 0 - ew_velocity
                    self.ew_velocity = ew_velocity

                if north_south_raw != 0:
                    if self._get_msg_byte(7) & 0x80:
                        ns_velocity = 0 - ns_velocity
                    self.ns_velocity = ns_velocity

                if east_west_raw != 0 and north_south_raw != 0:
                    self.velocity = int(round(math.sqrt((ns_velocity ** 2) + (ew_velocity ** 2))))
                    if self.cfg_use_metric:
                        self.velocity = self.KPH_PER_KNOT * self.velocity
                    if self.velocity != 0:
                        self.heading = int(round(math.atan2(ew_velocity, ns_velocity) * 180 / math.pi))
                        if self.heading < 0:
                            self.heading += 360
            if 3 <= sub_type <= 4:
                airspeed = ((self._get_msg_byte(7) & 0x7f) << 3) | (self._get_msg_byte(8) >> 5)
                if airspeed != 0:
                    airspeed -= 1
                    if sub_type == 4:  # supersonic
                        airspeed = airspeed << 2
                    self.velocity = airspeed
                if self._get_msg_byte(5) & 0x04:
                    self.heading = ((((self._get_msg_byte(5) & 0x03) << 8) | self._get_msg_byte(6)) * 45) >> 7

        elif self.TC_SURFACE_POS_5 <= self.type_code <= self.TC_AIRBORNE_POS_22:
            self.is_CPR_msg = True
            self.odd = True if self._get_msg_byte(6) & 0x04 else False

            self.raw_latitude = ((self._get_msg_byte(6) & 0x03) << 15) \
                                | (self._get_msg_byte(7) << 7) \
                                | (self._get_msg_byte(8) >> 1)
            self.raw_longitude = ((self._get_msg_byte(8) & 0x01) << 16) \
                                 | (self._get_msg_byte(9) << 8) \
                                 | (self._get_msg_byte(10))

            if self.TC_AIRBORNE_POS_9 <= self.type_code <= self.TC_AIRBORNE_POS_18:
                self.altitude = self._get_altitude()
                self.on_ground = False
            elif self.TC_AIRBORNE_POS_20 <= self.type_code <= self.TC_AIRBORNE_POS_22:
                self.altitude = self._get_altitude()
                self.on_ground = False
            elif self.TC_SURFACE_POS_5 <= self.type_code <= self.TC_SURFACE_POS_8:
                self.velocity = self._get_velocity()
                self.heading = self._get_heading()
                self.on_ground = True

        elif self.type_code == self.TC_RESERVED_TEST_23:
            if sub_type == 7:
                id_13 = (((self._get_msg_byte(5) << 8) | self._get_msg_byte(6)) & 0xFFF1) >> 3
                if id_13 != 0:
                    self.Squawk = parse_id13(id_13)

        elif self.type_code == self.TC_EXT_SQ_AIRCRFT_STATUS_28:
            if sub_type == 1:
                id_13 = ((self._get_msg_byte(5) << 8) | self._get_msg_byte(6)) & 0x1FFF
                if id_13 != 0:
                    self.Squawk = parse_id13(id_13)

    def decode_extended_squitter_msg(self):
        if self.capability == 0 or self.capability == 1 or self.capability == 6:
            self.decode_ADSB_msg()

    def decode_comm_bds_reply_msg(self):
        if self._get_msg_byte(4) == 0x20:
            self.call_sign = callsign(hex(self.msg)[2:-1])

    def decode_altitude_msg(self):
        ac_13 = ((self._get_msg_byte(2) << 8) | self._get_msg_byte(3)) & 0x1FFF
        if ac_13 != 0:
            altitude = parse_ac13(ac_13)
            self.altitude = self.METER_PER_FOOT * altitude if self.cfg_use_metric else altitude

    def decode_identity_msg(self):
        if self.TC_ID_CAT_D_1 <= self.type_code <= self.TC_ID_CAT_A_4:
            self.Squawk = self._get_identity()

    def decode_comm_bds_identity_msg(self):
        self.Squawk = self._get_identity()

    def decode_flight_status_msg(self):
        self.flight_status = self._get_msg_byte(0) & 0x07

    def _update_statistics(self):
        if self.downlink_format == self.DF_SHORT_AIR2AIR_SURVEILLANCE_0:
            basic.statistics.df_0 += 1
        elif self.downlink_format == self.DF_SURVEILLANCE_ALTITUDE_REPLY_4:
            basic.statistics.df_4 += 1
        elif self.downlink_format == self.DF_SURVEILLANCE_IDENTITY_REPLY_5:
            basic.statistics.df_5 += 1
        elif self.downlink_format == self.DF_LONG_AIR2AIR_SURVEILLANCE_16:
            basic.statistics.df_16 += 1
        elif self.downlink_format == self.DF_ADSB_MSG_17:
            basic.statistics.df_17 += 1
        elif self.downlink_format == self.DF_EXTENDED_SQUITTER_18:
            basic.statistics.df_18 += 1
        elif self.downlink_format == self.DF_COMM_BDS_ALTITUDE_REPLY_20:
            basic.statistics.df_20 += 1
        elif self.downlink_format == self.DF_COMM_BDS_IDENTITY_REPLY_21:
            basic.statistics.df_21 += 1

    def decode(self):
        if self.ICAO24 == 0:  # if ICAO24 is already set we do not re-compute it here, see run in Radar
            self.ICAO24 = hex(((self._get_msg_byte(1) << 16)
                               | (self._get_msg_byte(2) << 8)
                               | self._get_msg_byte(3)))[2:].rstrip('L')
        self.capability = self._get_msg_byte(0) & 0x07
        self.type_code = self._get_msg_byte(4) >> 3
        self.emitter_category = self._get_msg_byte(4) & 0x07
        self.parity = self.msg & 0xFFFFFF

        if self.downlink_format == self.DF_SHORT_AIR2AIR_SURVEILLANCE_0:
            self.decode_altitude_msg()
        elif self.downlink_format == self.DF_SURVEILLANCE_ALTITUDE_REPLY_4:
            self.decode_altitude_msg()
            self.decode_flight_status_msg()
        elif self.downlink_format == self.DF_SURVEILLANCE_IDENTITY_REPLY_5:
            self.decode_identity_msg()
            self.decode_flight_status_msg()
        elif self.downlink_format == self.DF_LONG_AIR2AIR_SURVEILLANCE_16:
            self.decode_altitude_msg()
        elif self.downlink_format == self.DF_ADSB_MSG_17:
            self.decode_ADSB_msg()
        elif self.downlink_format == self.DF_EXTENDED_SQUITTER_18:
            self.decode_extended_squitter_msg()
        elif self.downlink_format == self.DF_COMM_BDS_ALTITUDE_REPLY_20:
            self.decode_comm_bds_reply_msg()
            self.decode_altitude_msg()
            self.decode_flight_status_msg()
        elif self.downlink_format == self.DF_COMM_BDS_IDENTITY_REPLY_21:
            self.decode_comm_bds_reply_msg()
            self.decode_comm_bds_identity_msg()
            self.decode_flight_status_msg()

        self._update_statistics()
