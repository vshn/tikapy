**************************************************
tikapy, a python3 API client for MikroTik RouterOS
**************************************************

tikapy is a simple API client for MikroTik RouterOS written for python3.

============
Installation
============

.. code-block:: bash

    $ pip install tikapy

========
Examples
========

.. code-block:: python

    #!/usr/bin/python3
    
    from tikapy import TikapySslClient
    from pprint import pprint
    
    client = TikapySslClient('10.140.66.11', 8729)
    
    client.login('api-test', 'api123')
    pprint(client.talk(['/routing/ospf/neighbor/getall']))
