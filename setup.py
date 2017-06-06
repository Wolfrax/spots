from distutils.core import setup

setup(
    name='spots',
    version='1.0',
    py_modules=['basic', 'radar', 'squitter', 'tuner', 'test_CPR'],
    data_files=[('', ['adsb-packet.png',
                     'LICENSE.txt',
                     'modes1.bin',
                     'README.md',
                     'spots_config.json',
                     'squitter.json'])],
    url='',
    license='GPL',
    author='Mats Melander',
    author_email='mats.melander@gmail.com',
    description='A decoder for ADS-B messages on extended squitter at 1090MHz', requires=['flask']
)
