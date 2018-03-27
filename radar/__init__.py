from pkg_resources import get_distribution, DistributionNotFound
import os.path

VERSION = "2.3"

try:
    _dist = get_distribution('spots')
    dist_loc = os.path.normcase(_dist.location)
    here = os.path.normcase(__file__)
    if not here.startswith(os.path.join(dist_loc, 'spots')):
        raise DistributionNotFound
except DistributionNotFound:
    __version__ = VERSION
else:
    __version__ = _dist.version
