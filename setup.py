"""
tikapy setup module.
"""

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name='tikapy',
    version='0.1.0',
    description='A python client for the MikroTik RouterOS API',
    url='https://github.com/vshn/tikapy',
    author='Andre Keller',
    author_email='andre.keller@vshn.ch',
    # BSD 3-Clause License:
    # - http://opensource.org/licenses/BSD-3-Clause
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],

    packages=[
        'tikapy',
    ]

)
