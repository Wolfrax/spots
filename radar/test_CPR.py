import squitter


def main():
    Sq = squitter.Squitter()

    # Examples from
    #   https://adsb-decode-guide.readthedocs.io/en/latest/content/airborne-position.html
    #   http://www.lll.lu/~edward/edward/adsb/DecodingADSBposition.html

    # For (93000, 74158, 51372, 50194) expected result is latitude = 52.257, longitude: 3.919
    Sq.even_raw_latitude = 93000  # 92095
    Sq.odd_raw_latitude = 74158  # 88385
    Sq.even_raw_longitude = 51372  # 39846
    Sq.odd_raw_longitude = 50194  # 125818
    Sq.odd_time = 1
    Sq.even_time = 2  # Make sure that even msg is later than odd

    if Sq.decodeCPR():
        print "latitude: {} longitude: {}".format(Sq['latitude'], Sq['longitude'])
        print "Expected latitude: 52.257 longitude: 3.919"

    # For (92095, 88385, 39846, 125818) expected result is latitude = 10.216 longitude: 123.889
    Sq.even_raw_latitude = 92095
    Sq.odd_raw_latitude = 88385
    Sq.even_raw_longitude = 39846
    Sq.odd_raw_longitude = 125818
    Sq.odd_time = 1
    Sq.even_time = 2  # Make sure that even msg is later than odd

    if Sq.decodeCPR():
        print "Got latitude: {} longitude: {}".format(Sq['latitude'], Sq['longitude'])
        print "Expected latitude: 10.216 longitude: 123.889"

    m1 = [0, 0x8D40621D58C386435CC412692AD6]  # Odd
    m2 = [0, 0x8D40621D58C382D690C8AC2863A7]  # Even

    Sq1 = squitter.Squitter()
    Sq1.parse(m1)
    Sq1.decode()

    Sq2 = squitter.Squitter()
    Sq2.parse(m2)
    Sq2.decode()

    Sq1.update(Sq2)  # Expected result is latitude = 52.257, longitude: 3.919
    if Sq1.decodeCPR():
        print "latitude: {} longitude: {}".format(Sq1['latitude'], Sq1['longitude'])
        print "Expected latitude: 52.257 longitude: 3.919"

    m3 = [0, 0x8D40621D58C382D690C8AC2863A7]
    Sq3 = squitter.Squitter()
    Sq3.cfg_latitude = 52.258
    Sq3.cfg_longitude = 3.918
    Sq3.parse(m3)
    Sq3.decode()
    if Sq3.decodeCPR_relative():
        print "latitude: {} longitude: {}".format(Sq3['latitude'], Sq3['longitude'])
        print "Expected latitude: 52.25720 longitude: 3.91937"


if __name__ == '__main__':
    main()
