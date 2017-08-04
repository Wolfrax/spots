from setuptools import setup, find_packages
from .radar import __version__

with open('README') as f:
    long_description = f.read()

setup(
    name='spots',
    version=__version__,
    packages=find_packages(),
    data_files=[('', ['adsb-packet.png', 'spots.png', 'LICENSE.txt', 'README.md', 'README']),
                ('client', ['map.html', 'spots.html', 'spots.js']),
                ('radar', ['modes1.bin', 'radar.conf', 'spots_config.json', 'spots_emitter.conf', 'squitter.json'])],
    install_requires=['docutils>=0.3', 'Flask', 'pyrtlsdr'],
    url='https://github.com/Wolfrax/spots',
    license='GPL',
    author='Mats Melander',
    author_email='mats.melander@gmail.com',
    classifiers=['Development Status :: 5 - Production/Stable',
                 'Intended Audience :: Developers',
                 'Programming Language :: Python :: 2.7',],
    description='A decoder for ADS-B messages on extended squitter at 1090MHz',
    long_description=long_description,
    keywords='ads-b adsb dump1090 mode-s modes'
)
