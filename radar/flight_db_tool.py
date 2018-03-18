import os
import simplejson
import sys
import argparse
import pprint


class FlightDB:
    """
    The FlightDB class is a simple persistent storage of flight data.

    It stores data int a json file and sends the top 10 (configurable) flights to the client
    """

    def __init__(self, loc):
        location = os.path.expanduser(loc)
        self.loc = loc
        if os.path.exists(location):
            self.db = simplejson.load(open(self.loc, 'rb'))
        else:
            print("File {} does not exists!".format(loc))
            sys.exit(0)

    def filter(self, limit, lte=True):
        res = {}
        for k, v in self.db['flights'].iteritems():
            if lte:
                if v <= limit:
                    res[k] = v
            else:
                if v >= limit:
                    res[k] = v
        return res

    def max_val(self):
        return self.db['flights'][max(self.db['flights'], key=self.db['flights'].get)]

    def get_tot_cnt(self):
        return self.db['total_cnt']

    def get_version(self):
        return self.db['version']

    def get_start_date(self):
        return self.db['start_date']

    def get_no_flights(self):
        return len(self.db['flights'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="the database (json) file to use")
    args = parser.parse_args()
    pp = pprint.PrettyPrinter(indent=4)

    db = FlightDB(args.file)
    print("Info on {}".format(args.file))
    print("Version is {}, start date is {}, no of fligths are {}, total count is {}".format(db.get_version(),
                                                                                            db.get_start_date(),
                                                                                            db.get_no_flights(),
                                                                                            db.get_tot_cnt()))
    print("============")
    print

    rare = db.filter(1)
    print("All the rare flights are:")
    pp.pprint(rare)
    print("============")
    print

    max = db.max_val()
    common = db.filter(max - 10, lte=False)
    print("The most common flights are:")
    pp.pprint(common)
    print("============")
    print

    print("That's all!")



