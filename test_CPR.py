import basic
import math


def CPR_NL(lat):
    lat = abs(lat)
    if lat >= max(basic.ADSB.NL):
        return 1
    elif lat <= min(basic.ADSB.NL):
        return len(basic.ADSB.NL) + 1
    else:
        return basic.ADSB.NL.index(max(filter(lambda x: x < lat, basic.ADSB.NL))) + 1


def decodeCPR(odd_msg, even_msg):
    # We assume that odd_msg is consistent with even_msg on 'on_ground'
    air_dlat = 90.0 if odd_msg.on_ground else 360.0
    air_dlat_0 = air_dlat / 60.0
    air_dlat_1 = air_dlat / 59.0
    lat0 = even_msg.raw_latitude
    lat1 = odd_msg.raw_latitude
    lon0 = even_msg.raw_longitude
    lon1 = odd_msg.raw_longitude

    j = int(math.floor(((59 * lat0 - 60 * lat1) / 131072.0) + 0.5))

    rlat0 = air_dlat_0 * (j % 60 + lat0 / 131072.0)  # 10.2157745361328
    rlat1 = air_dlat_1 * (j % 59 + lat1 / 131072.0)  # 10.2162144547802

    if odd_msg.on_ground:
        surface_rlat = odd_msg.latitude if odd_msg.latitude != 0 else odd_msg.cfg_latitude
        surface_rlon = odd_msg.longitude if odd_msg.longitude != 0 else odd_msg.cfg_longitude
        rlat0 += math.floor(surface_rlat / 90.0) * 90.0
        rlat1 += math.floor(surface_rlat / 90.0) * 90.0
    else:  # Adjust if we are on southern hemisphere by substracting 360 from latitude
        if rlat0 >= 270:
            rlat0 -= 360
        if rlat1 >= 270:
            rlat1 -= 360

    if rlat0 < -90 or rlat0 > 90 or rlat1 < -90 or rlat1 > 90:
        return None
    if CPR_NL(rlat0) != CPR_NL(rlat1):
        return None  # The NL latitude value for odd and even frames must be equal

    ni = max(CPR_NL(rlat1) - 1, 1)  # 58
    m = int(math.floor((((lon0 * (CPR_NL(rlat1) - 1)) - (lon1 * CPR_NL(rlat1))) / 131072.0) + 0.5))  # -39
    if odd_msg.on_ground:
        longitude = 90.0
    else:
        longitude = (360.0 / ni) * ((m % ni) + lon1 / 131072.0)
    latitude = rlat1

    if odd_msg.on_ground:
        longitude += math.floor(surface_rlon / 90.0) * 90.0
    elif longitude > 180:
        longitude -= 360

    return {'latitude': latitude, 'longitude': longitude}


class CPR(basic.ADSB):
    def __init__(self):
        basic.ADSB.__init__(self)

        self.raw_latitude = 0
        self.raw_longitude = 0
        self.latitude = 0
        self.longitude = 0
        self.on_ground = False
        self.odd = False
        self.cfg_latitude = 0
        self.cfg_longitude = 0

def main():
    CPR1 = CPR()
    CPR2 = CPR()

    CPR1.raw_latitude = 88385
    CPR1.raw_longitude = 125818
    CPR1.odd = True

    CPR2.raw_latitude = 92095
    CPR2.raw_longitude = 39846
    CPR2.odd = False

    res = decodeCPR(CPR1, CPR2)

    if res is not None:
        print "latitude: {}, longitude: {}".format(res['latitude'], res['longitude'])

if __name__ == '__main__':
    main()