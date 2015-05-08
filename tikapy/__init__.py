#!/usr/bin/python3

#
# Copyright (c) 2015, VSHN AG, info@vshn.ch
# Licensed under "BSD 3-Clause". See LICENSE file.
#
# Authors:
#  - Andre Keller <andre.keller@vshn.ch>
#

"""
MikroTik RouterOS Python API Clients
"""

import logging
import socket
import ssl
from .api import ApiError, ApiRos, ApiUnrecoverableError

LOG = logging.getLogger(__name__)


class ClientError(Exception):
    """
    Exception returned when a API client interaction fails.
    """
    pass


class TikapyBaseClient():
    """
    Base class for functions shared between the SSL and non-SSL API client
    """

    def __init__(self):
        """
        Constructor. Initialize instance variables.
        """
        self._address = None
        self._port = None
        self._base_sock = None
        self._sock = None
        self._api = None

    @property
    def address(self):
        """
        Address of the remote API.

        :return: string - address of the remote API.
        """
        return self._address

    @address.setter
    def address(self, value):
        """
        Address of the remote API.
        """
        self._address = value

    @property
    def port(self):
        """
        Port of the remote API.
        :return:
        """
        return self._port

    @port.setter
    def port(self, value):
        """
        Port of the remote API.

        :raises: ValueError - if invalid port number is specified
        """
        try:
            if not 0 < value < 65536:
                raise ValueError('%d is not a valid port number' % value)
            self._port = value
        except ValueError as exc:
            raise ValueError('invalid port number specified') from exc

    def __del__(self):
        """
        Destructor. Tries to disconnect socket if it is still open.
        """
        self.disconnect()

    def disconnect(self):
        """
        Disconnect/closes open sockets.
        """
        try:
            if self._sock:
                self._sock.close()
        except socket.error:
            pass
        try:
            if self._base_sock:
                self._base_sock.close()
        except socket.error:
            pass

    def _connect_socket(self):
        """
        Connect the base socket.

        If self.address is a hostname, this function will loop through
        all available addresses until it can establish a connection.

        :raises: ClientError - if address/port has not been set
                             - if no connection to remote socket
                               could be established.
        """
        if not self.address:
            raise ClientError('address has not been set')
        if not self.port:
            raise ClientError('address has not been set')

        for family, socktype, proto, _, sockaddr in \
                socket.getaddrinfo(self.address,
                                   self.port,
                                   socket.AF_UNSPEC,
                                   socket.SOCK_STREAM):

            try:
                self._base_sock = socket.socket(family, socktype, proto)
            except socket.error:
                self._base_sock = None
                continue

            try:
                self._base_sock.connect(sockaddr)
            except socket.error:
                self._base_sock.close()
                self._base_sock = None
                continue
            break

        if self._base_sock is None:
            LOG.error('could not open socket')
            raise ClientError('could not open socket')

    def _connect(self):
        """
        Connects the socket and stores the result in self._sock.

        This is meant to be sub-classed if a socket needs to be wrapped,
        f.e. with an SSL handler.
        """
        self._connect_socket()
        self._sock = self._base_sock

    def login(self, user, password):
        """
        Connects to the API and tries to login the user.

        :param user: Username for API connections
        :param password: Password for API connections
        :raises: ClientError - if login failed
        """
        self._connect()
        self._api = ApiRos(self._sock)
        try:
            self._api.login(user, password)
        except (ApiError, ApiUnrecoverableError) as exc:
            raise ClientError('could not login') from exc

    def talk(self, words):
        """
        Send command sequence to the API.

        :param words: List of command sequences to send to the API
        :returns: dict containing response.
        :raises: ClientError - If client could not talk to remote API.
                 ValueError - On invalid input.
        """
        if isinstance(words, list) and all(isinstance(x, str) for x in words):
            try:
                return self.tik_to_json(self._api.talk(words))
            except (ApiError, ApiUnrecoverableError) as exc:
                raise ClientError('could not talk to api') from exc
        raise ValueError('words needs to be a list of strings')

    @staticmethod
    def tik_to_json(tikoutput):
        """
        Converts MikroTik RouterOS output to python dict / JSON.

        :param tikoutput:
        :return: doct containing response.
        """
        try:
            return {
                d['.id'][1:]: d for d in ([x[1] for x in tikoutput])
                if '.id' in d.keys()}
        except (TypeError, IndexError) as exc:
            raise ClientError('unable to convert api output to json') from exc


class TikapyClient(TikapyBaseClient):
    """
    RouterOS API Client.
    """

    def __init__(self, address, port=8728):
        """
        Initialize client.

        :param address: Remote device address (maybe a hostname)
        :param port: Remote device port (defaults to 8728)
        """
        super().__init__()
        self.address = address
        self.port = port


class TikapySslClient(TikapyBaseClient):
    """
    RouterOS SSL API Client.
    """

    def __init__(self, address, port=8729):
        """
        Initialize client.

        :param address: Remote device address (maybe a hostname)
        :param port: Remote device port (defaults to 8728)
        """
        super().__init__()
        self.address = address
        self.port = port

    def _connect(self):
        """
        Connects a ssl socket.
        """
        self._connect_socket()
        self._sock = ssl.wrap_socket(self._base_sock)
