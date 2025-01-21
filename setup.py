import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="unifi_respondd",
    version="VERSION",
    author="Annika Wickert",
    author_email="aw@awlnx.space",
    description=("A tool to display Unifi APs on Freifunk maps."),
    license="GPLv3",
    keywords="Unifi Freifunk",
    url="http://packages.python.org/unifi_respondd",
    packages=["unifi_respondd"],
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    include_package_data=True,
    install_requires=[
        "pyunifi==2.21",
        "geopy==2.2.0",
        "pyyaml==6.0",
        "dataclasses_json==0.6.7",
    ],
)
