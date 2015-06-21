#!/usr/bin/env python3

import asyncio
import binascii
import hashlib
import logging
import socket
LOG = logging.getLogger(__name__)
#logging.basicConfig(level=logging.DEBUG)


class ApiError(Exception):
    pass
class ApiUnrecoverableError(Exception):
    pass
class ClientError(Exception):
    """
    Exception returned when a API client interaction fails.
    """
    pass



class TikapyClient():
    """
    RouterOS API Client.
    """

    def __init__(self, address, port=8728):
        self._address = address
        self._port = port
        self._base_sock = None
        self._sock = None
        self._api = None
        self._transport = None
        self._protocol = None
        self._loop = asyncio.get_event_loop()


    def __del__(self):
        """
        Destructor. Tries to disconnect socket if it is still open.
        """
        self._loop.stop()

    def _connect_socket(self):
        """
        Connect the base socket.

        If self.address is a hostname, this function will loop through
        all available addresses until it can establish a connection.

        :raises: ClientError - if address/port has not been set
                             - if no connection to remote socket
                               could be established.
        """
        if not self._address:
            raise ClientError('address has not been set')
        if not self._port:
            raise ClientError('address has not been set')

        for family, socktype, proto, _, sockaddr in \
                socket.getaddrinfo(self._address,
                                   self._port,
                                   socket.AF_UNSPEC,
                                   socket.SOCK_STREAM):

            try:
                self._base_sock = socket.socket(family, socktype, proto)
            except socket.error:
                self._base_sock = None
                continue

            try:
                self._base_sock.connect(sockaddr)
                self._base_sock.setblocking(False)
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
        # self._api = ApiRos(self._sock)
        # try:
        #     self._api.login(user, password)
        # except (ApiError, ApiUnrecoverableError) as exc:
        #     raise ClientError('could not login') from exc


    @staticmethod
    def tik_to_json(tikoutput):
        """
        Converts MikroTik RouterOS output to python dict / JSON.

        :param tikoutput:
        :return: dict containing response or ID.
        """
        try:
            if tikoutput[0][0] == '!done':
                return tikoutput[0][1]['ret']
        except (IndexError, KeyError):
            pass
        try:
            return {
                d['.id'][1:]: d for d in ([x[1] for x in tikoutput])
                if '.id' in d.keys()}
        except (TypeError, IndexError) as exc:
            raise ClientError('unable to convert api output to json') from exc


class RosProtocol(asyncio.Protocol):


    def __init__(self):
        self._tag = 0
        self._queries = {}
        self._replies = {}


    def connection_made(self, transport):
        self.transport = transport
        LOG.debug("connection made")


    def data_received(self, data):
        data = data.decode('latin-1', 'replace')
        pos = 0
        while True:
            pos, tikout = self._read_sentence(data)
            self._handle_response(tikout)
            if pos < len(data):
                data = data[pos:]
            else:
                break



    @asyncio.coroutine
    def query(self, words):
        self._tag += 1
        self._talk(words, self._tag)
        f = asyncio.Future()
        self._queries[self._tag] = f
        response = yield from f
        return response

    @asyncio.coroutine
    def login(self, username, password):
        """
        Perform API login

        Args:
            username - Username used to login
            password - Password used to login
        """

        # request login
        # Mikrotik answers with a challenge in the 'ret' attribute
        # 'ret' attribute accessible as attrs['ret']
        self._tag += 1
        self._talk(['/login'], self._tag)

        f = asyncio.Future()
        self._queries[self._tag] = f

        response_dict = yield from f
        _, response = response_dict.popitem()

        ret = response['ret']
        # Prepare response for challenge-response login
        # response is MD5 of 0-char + plaintext-password + challange
        response = hashlib.md5()
        response.update(b'\x00')
        response.update(password.encode('latin-1'))
        response.update(binascii.unhexlify(ret.encode('latin-1')))
        response = "00" + binascii.hexlify(response.digest()).decode('latin-1')

        # send response & login request
        self._tag += 1
        self._talk([
            "/login",
            "=name=%s" % username,
            "=response=%s" % response
        ], self._tag)

        f = asyncio.Future()
        self._queries[self._tag] = f

        response = yield from f

    def _talk(self, words, tag):
        """
        Communicate with the API

        Args:
            words - List of API words to send
        """
        if not isinstance(words, list):
            raise ApiError('words need to be a list')
        words.append(".tag=%d" % tag)
        self._write_sentence(words)


    def _write_sentence(self, words):
        """
        writes a sentence word by word to API socket.

        Ensures sentence is terminated with a zero-length word.

        Args:
            words - List of API words to send
        """
        for word in words:
            self.write_word(word)
        # write zero-length word to indicate end of sentence.
        self.write_word('')

    def _read_sentence(self, data):
        """
        reads sentence word by word from API socket.

        API uses zero-length word to terminate sentence, so words are read
        until zero-length word is received.

        Returns:
            words - List of API words read from socket
        """
        words = []
        pos = 0
        while len(data) > pos:
            pos, word = self._read_word(pos, data)
            if word == '':
                break
            words.append(word)
        return pos, words

    def write_word(self, word):
        """
        writes word to API socket

        The MikroTik API expects the length of the word to be sent over the
        wire using a special encoding followed by the word itself.

        See http://wiki.mikrotik.com/wiki/Manual:API#API_words for details.

        Args:
            word
        """

        length = len(word)
        LOG.debug("<<< %s", word)
        # word length < 128
        if length < 0x80:
            self.write_sock(chr(length))
        # word length < 16384
        elif length < 0x4000:
            length |= 0x8000
            self.write_sock(chr((length >> 8) & 0xFF))
            self.write_sock(chr(length & 0xFF))
        # word length < 2097152
        elif length < 0x200000:
            length |= 0xC00000
            self.write_sock(chr((length >> 16) & 0xFF))
            self.write_sock(chr((length >> 8) & 0xFF))
            self.write_sock(chr(length & 0xFF))
        # word length < 268435456
        elif length < 0x10000000:
            length |= 0xE0000000
            self.write_sock(chr((length >> 24) & 0xFF))
            self.write_sock(chr((length >> 16) & 0xFF))
            self.write_sock(chr((length >> 8) & 0xFF))
            self.write_sock(chr(length & 0xFF))
        # word length < 549755813888
        elif length < 0x8000000000:
            self.write_sock(chr(0xF0))
            self.write_sock(chr((length >> 24) & 0xFF))
            self.write_sock(chr((length >> 16) & 0xFF))
            self.write_sock(chr((length >> 8) & 0xFF))
            self.write_sock(chr(length & 0xFF))
        else:
            raise ApiUnrecoverableError("word-length exceeded")
        self.write_sock(word)

    def _read_word(self, pos, data):
        """
        read word from API socket

        The MikroTik API sends the length of the word to be received over the
        wire using a special encoding followed by the word itself.

        This function will first determine the length, and then read the
        word from the socket.

        See http://wiki.mikrotik.com/wiki/Manual:API#API_words for details.

        """
        # value of first byte determines how many bytes the encoded length
        # of the words will have.

        # we read the first char from the socket and determine its ASCII code.
        # (ASCII code is used to encode the length. Char "a" == 65 f.e.
        length = ord(data[pos])
        # if most significant bit is 0
        # -> length < 128, no additional bytes need to be read
        if (length & 0x80) == 0x00:
            pass
        # if the two most significant bits are 10
        # -> length is >= 128, but < 16384
        elif (length & 0xC0) == 0x80:
            # unmask and shift the second lowest byte
            length &= ~0xC0
            length <<= 8
            # read the lowest byte
            pos += 1
            length += ord(data[pos])
        # if the three most significant bits are 110
        # -> length is >= 16384, but < 2097152
        elif (length & 0xE0) == 0xC0:
            # unmask and shift the third lowest byte
            length &= ~0xE0
            length <<= 8
            # read and shift second lowest byte
            pos += 1
            length += ord(data[pos])
            length <<= 8
            # read lowest byte
            length += ord(data[2])
        # if the four most significant bits are 1110
        # length is >= 2097152, but < 268435456
        elif (length & 0xF0) == 0xE0:
            # unmask and shift the fourth lowest byte
            length &= ~0xF0
            length <<= 8
            # read and shift third lowest byte
            pos += 1
            length += ord(data[pos])
            length <<= 8
            # read and shift second lowest byte
            pos += 1
            length += ord(data[pos])
            length <<= 8
            # read lowest byte
            pos += 1
            length += ord(data[pos])
        # if the five most significant bits are 11110
        # length is >= 268435456, but < 4294967296
        elif (length & 0xF8) == 0xF0:
            # read and shift fourth lowest byte
            pos += 1
            length = ord(data[pos])
            length <<= 8
            # read and shift third lowest byte
            pos += 1
            length += ord(data[pos])
            length <<= 8
            # read and shift second lowest byte
            pos += 1
            length += ord(data[pos])
            length <<= 8
            # read lowest byte
            pos += 1
            length += ord(data[pos])
        else:
            raise ApiUnrecoverableError("unknown control byte received")

        # read actual word from socket, using length determined above
        pos += 1
        ret = data[pos:length+pos]
        LOG.debug(">>> %s", ret)
        return pos + length, ret

    def write_sock(self, string):
        """
        write string to API socket

        Args:
            string - String to send
        """
        self.transport.write(bytes(string, 'latin-1'))

    def read_sock(self, length):
        """
        read string with specified length from API socket

        Args:
            length - Number of chars to read from socket
        Returns:
            string - String as read from socket
        """
        string = ''
        while len(string) < length:
            # read data from socket with a maximum buffer size of 4k
            chunk = self.transport.sock.recv(min(length - len(string), 4096))
            if not chunk:
                raise ApiUnrecoverableError("could not read from socket")
            string = string + chunk.decode('latin-1', 'replace')
        return string

    def _handle_response(self, tikoutput):
        """
        Converts MikroTik RouterOS output to python dict / JSON.

        :param tikoutput:
        :return: dict containing response or ID.
        """

        reply = tikoutput.pop(0)
        attributes = {}
        for word in tikoutput:
            try:
                second_eq_pos = word.index('=', 1)
            except IndexError:
                attributes[word] = ''
            else:
                if word.startswith('.'):
                    attributes[word[:second_eq_pos]] = word[second_eq_pos + 1:]
                else:
                    attributes[word[1:second_eq_pos]] = word[second_eq_pos + 1:]
        if '.tag' in attributes.keys():
            id = int(attributes['.tag'])
            self._replies.setdefault(id, []).append(attributes)
            if reply == '!done':
                future = self._queries.get(id, None)
                if future is not None:
                    del self._queries[id]
                    future.set_result(self.tik_to_json(self._replies[id]))
                    del self._replies[id]

    @staticmethod
    def tik_to_json(tikoutput):
        jsonoutput = {}
        for result in tikoutput:
            if not '.id' in result.keys():
                jsonoutput["tag-%s" % result['.tag']] = result
            else:
                jsonoutput[result['.id']] = result
        return jsonoutput

@asyncio.coroutine
def run():
    loop = asyncio.get_event_loop()
    transport, protocol = yield from loop.create_connection(RosProtocol, '10.144.1.14', 8728)
    yield from protocol.login('api-test', 'api123')
    response = yield from protocol.query(['/interface/getall'])
    from pprint import pprint
    pprint(response)
    transport.close()

def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
    loop.stop()
    loop.close()

if __name__ == '__main__':
    main()
