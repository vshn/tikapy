tikapy
======

tikapy is a simple API client for MikroTik RouterOS written in python3.

|travis_ci|


Installation
------------

.. code-block:: bash

    $ pip install tikapy

Examples
--------

.. code-block:: python

    #!/usr/bin/python3
    
    from tikapy import TikapySslClient
    from pprint import pprint
    
    client = TikapySslClient('10.140.66.11', 8729)
    
    client.login('api-test', 'api123')
    pprint(client.talk(['/routing/ospf/neighbor/getall']))


.. |travis_ci| image:: https://api.travis-ci.org/vshn/tikapy.svg?branch=master
   :target: https://travis-ci.org/vshn/tikapy
   :alt: Travis CI build status (master)
