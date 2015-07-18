#!/usr/bin/env python3

"""
asyncio implementation of MikroTik RouterOS API
"""

import asyncio
import binascii
import hashlib
import itertools
import logging
LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class ApiError(Exception):
    """
    Exception returned when an API call fails
    """


class ClientError(Exception):
    """
    Exception returned when a API client interaction fails.
    """


class RosProtocol(asyncio.Protocol):
    """
    asyncio protocol implementing MikroTik RouterOS API
    """

    def __init__(self):
        """
        Initialize protocol instance
        """
        self._queries = {}
        self._replies = {}
        self._tag = itertools.count(start=1)
        self._transport = None

    def connection_made(self, transport):
        """
        callback triggered when a connection is established.

        :param transport: Transport representing the connection.
        """
        self._transport = transport
        LOG.debug("connection made")

    def data_received(self, data):
        """
        callback triggered when data is received

        :param data: Data received from socket
        """
        data = data.decode('latin-1', 'replace')
        while True:
            pos, tikout = self._read_sentence(data)
            try:
                self._handle_response(tikout)
            except ApiError:
                break
            if pos < len(data):
                data = data[pos:]
            else:
                break

    @asyncio.coroutine
    def query(self, words):
        """
        Send query RouterOS API

        :param words: Words to send to API
        :type words list
        :return: API response
        :rtype: dict
        """
        #
        tag = next(self._tag)
        future = asyncio.Future()
        self._queries[tag] = future
        self._talk(words, tag)
        response = yield from future
        return response

    @asyncio.coroutine
    def login(self, username, password):
        """
        Performs API login

        :param username: API user
        :type username str
        :param password: Password for API user
        :type password str
        """

        # request login
        # Mikrotik answers with a challenge in the 'ret' attribute
        tag = next(self._tag)
        self._talk(['/login'], tag)

        future = asyncio.Future()
        self._queries[tag] = future

        response_dict = yield from future
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
        tag = next(self._tag)
        self._talk([
            "/login",
            "=name=%s" % username,
            "=response=%s" % response
        ], tag)

        future = asyncio.Future()
        self._queries[tag] = future
        yield from future

    def _talk(self, words, tag):
        """
        Sends API words to transport, tagged with an identifier.

        :param words: List of API words to send to transport
        :type words list
        :param tag: Identifying tag
        :type tag int
        """
        if not isinstance(words, list):
            raise ApiError('words need to be a list')
        words.append(".tag=%d" % tag)
        self._write_sentence(words)

    def _write_sentence(self, words):
        """
        writes a sentence word by word to API socket (asyncio Transport).

        Ensures sentence is terminated with a zero-length word.

        :param words: List of API words to send to transport
        :type words list
        """
        for word in words:
            self.write_word(word)
        # write zero-length word to indicate end of sentence.
        self.write_word('')

    def _read_sentence(self, data):
        """
        reads sentence word by word from stream.

        API uses zero-length word to terminate sentence, so words are read
        until zero-length word is received.

        :param data: Stream to read from
        :type data str
        :return: Current position in stream and words read from API
        :rtype: tuple (pos as int, words as list)
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
        writes word to API socket (asyncio Transport)

        The MikroTik API expects the length of the word to be sent over the
        wire using a special encoding followed by the word itself.

        See http://wiki.mikrotik.com/wiki/Manual:API#API_words for details.

        :param word: Word to write to transport
        :type word str
        """
        length = len(word)
        LOG.debug("<<< %s", word)
        # word length < 128
        if length < 0x80:
            self.write_to_transport(chr(length))
        # word length < 16384
        elif length < 0x4000:
            length |= 0x8000
            self.write_to_transport(chr((length >> 8) & 0xFF))
            self.write_to_transport(chr(length & 0xFF))
        # word length < 2097152
        elif length < 0x200000:
            length |= 0xC00000
            self.write_to_transport(chr((length >> 16) & 0xFF))
            self.write_to_transport(chr((length >> 8) & 0xFF))
            self.write_to_transport(chr(length & 0xFF))
        # word length < 268435456
        elif length < 0x10000000:
            length |= 0xE0000000
            self.write_to_transport(chr((length >> 24) & 0xFF))
            self.write_to_transport(chr((length >> 16) & 0xFF))
            self.write_to_transport(chr((length >> 8) & 0xFF))
            self.write_to_transport(chr(length & 0xFF))
        # word length < 549755813888
        elif length < 0x8000000000:
            self.write_to_transport(chr(0xF0))
            self.write_to_transport(chr((length >> 24) & 0xFF))
            self.write_to_transport(chr((length >> 16) & 0xFF))
            self.write_to_transport(chr((length >> 8) & 0xFF))
            self.write_to_transport(chr(length & 0xFF))
        else:
            raise ApiError("word-length exceeded")
        self.write_to_transport(word)

    @staticmethod
    def _read_word(pos, data):
        """
        read encoded word from a stream

        The MikroTik API sends the length of the word to be received over the
        wire using a special encoding followed by the word itself.

        This function will first determine the length, and then read the
        word from the socket.

        See http://wiki.mikrotik.com/wiki/Manual:API#API_words for details.

        :param pos: Initial offset, where in the stream to start reading
        :type pos int
        :param data: Stream to read from
        :type data str
        :return: Returns new offset and the decoded word as a tuple
        :rtype: tuple
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
            pos += 1
            length += ord(data[pos])
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
            raise ApiError("unknown control byte received")

        # read actual word from socket, using length determined above
        pos += 1
        ret = data[pos:length+pos]
        LOG.debug(">>> %s", ret)
        return pos + length, ret

    def write_to_transport(self, string):
        """
        write string to API socket (asyncio Transport)

        :param string: Data to be written to the transport
        :type string str
        """
        self._transport.write(bytes(string, 'latin-1'))

    @staticmethod
    def _extract_attribute(rawoutput):
        """
        Extracts the word attributes from the raw RouterOS API output.

        :param rawoutput: Output as received on the socket
        :type rawoutput list
        :return: Extracted attributes or simple word if no attributes are found
        :rtype: dict | str
        """
        attributes = {}
        for word in rawoutput:
            try:
                second_eq_pos = word.index('=', 1)
            except IndexError:
                attributes[word] = ''
            except ValueError:
                attributes = str(word)
            else:
                if word.startswith('.'):
                    attributes[word[:second_eq_pos]] = word[second_eq_pos + 1:]
                else:
                    attributes[word[1:second_eq_pos]] = word[second_eq_pos + 1:]
        return attributes

    def _handle_response(self, rawoutput):
        """
        Converts MikroTik RouterOS API output to python dict.

        Results are stored in the futures matching the original query.

        :param rawoutput: Output as received from socket.
        :type rawoutput list
        """
        reply = rawoutput.pop(0)
        attributes = self._extract_attribute(rawoutput)

        if reply == '!fatal':
            if isinstance(attributes, str):
                fatal = ApiError(attributes)
            else:
                fatal = ApiError("Unknown error occured")
            for _, future in self._queries.items():
                if future is not None:
                    future.set_exception(fatal)
                    raise fatal
            raise fatal

        if '.tag' in attributes.keys():
            query_id = int(attributes['.tag'])
            future = self._queries.get(query_id, None)
            self._replies.setdefault(query_id, []).append(attributes)
            if reply == '!done':
                if future is not None:
                    del self._queries[query_id]
                    future.set_result(
                        self.index_api_reply(self._replies[query_id])
                    )
                    del self._replies[query_id]
            elif reply == '!trap':
                if future is not None:
                    future.set_exception(ApiError(attributes['message']))
                    raise ApiError(attributes['message'])

    @staticmethod
    def index_api_reply(api_reply):
        """
        Indexing Mikrotik API replies.

        :param api_reply: List of dicts containing API replies.
        :type api_reply list
        :return: API replies indexed by .id or .tag if .id is not part of reply
        :rtype: dict
        """
        indexed_replies = {}
        for result in api_reply:
            if '.id' not in result.keys():
                indexed_replies["tag-%s" % result['.tag']] = result
            else:
                indexed_replies[result['.id']] = result
        return indexed_replies


# THE FOLLOWING LINES ARE DEMO/TEST CODE THAT IS BEING REMOVED
@asyncio.coroutine
def run():
    loop = asyncio.get_event_loop()
    transport = None
    try:
        transport, protocol = yield from loop.create_connection(RosProtocol, '10.144.1.14', 8728)
        yield from protocol.login('api-test', 'api123')
        response = yield from protocol.query(['/interface/getall'])
        return response
    except ApiError as exc:
        raise ClientError(exc) from exc
    finally:
        if isinstance(transport, asyncio.transports.Transport):
            transport.close()


def main():
    loop = asyncio.get_event_loop()
    try:
        bla = loop.run_until_complete(run())
        from pprint import pprint
        pprint(bla)
    except ClientError as exc:
        print("tikapy error occured: %s" % exc)
    finally:
        loop.stop()
        loop.close()

if __name__ == '__main__':
    main()
