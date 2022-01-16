import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "unifi_respondd",
    version = "0.0.5",
    author = "Annika Wickert",
    author_email = "aw@awlnx.space",
    description = ("A tool to display Unifi APs on Freifunk maps."),
    license = "GPLv3",
    keywords = "Unifi Freifunk",
    url = "http://packages.python.org/unifi_respondd",
    packages=['unifi_respondd'],
    long_description=read('README.md'),
    include_package_data=True,
)