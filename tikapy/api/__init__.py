#!/usr/bin/python3

#
# Copyright (c) 2015, VSHN AG, info@vshn.ch
# Licensed under "BSD 3-Clause". See LICENSE file.
#
# Authors:
#  - Andre Keller <andre.keller@vshn.ch>
#

"""
MikroTik Router OS Python API
"""

import binascii
import hashlib
import logging

LOG = logging.getLogger(__name__)


class ApiError(Exception):
    """
    Exception returned when API call fails.

    (!trap event)
    """
    pass


class ApiUnrecoverableError(Exception):
    """
    Exception returned when API call fails in an unrecovarable manner.

    (!fatal event)
    """
    pass


class ApiRos:
    """
    MikroTik Router OS Python API base class

    For a basic understanding of this code, its important to read through
    http://wiki.mikrotik.com/wiki/Manual:API.

    Within MikroTik API 'words' and 'sentences' have a very specific meaning
    """

    def __init__(self, sock):
        """
        Initialize base class.

        Args:
            sock - Socket (should already be opened and connected)
        """
        self.sock = sock
        self.currenttag = 0

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
        _, attrs = self.talk(["/login"])[0]

        # Prepare response for challenge-response login
        # response is MD5 of 0-char + plaintext-password + challange
        response = hashlib.md5()
        response.update(b'\x00')
        response.update(password.encode('UTF-8'))
        response.update(binascii.unhexlify((attrs['ret']).encode('UTF-8')))
        response = "00" + binascii.hexlify(response.digest()).decode('UTF-8')

        # send response & login request
        self.talk(["/login",
                   "=name=%s" % username,
                   "=response=%s" % response])

    def talk(self, words):
        """
        Communicate with the API

        Args:
            words - List of API words to send
        """
        if not words:
            return

        # Write sentence to API
        self.write_sentence(words)

        replies = []

        # Wait for reply
        while True:
            # read sentence
            sentence = self.read_sentence()

            # empty sentences are ignored
            if len(sentence) == 0:
                continue

            # extract first word from sentence.
            # this indicates the type of reply:
            #  - !re
            #    Replay
            #  - !done
            #    Acknowledgement
            #  - !trap
            #    API Error
            #  - !fatal
            #    Unrecoverable API Error
            reply = sentence.pop(0)

            attrs = {}
            # extract attributes from the words replied by the API
            for word in sentence:
                # try to determine if there is a second equal sign in the
                # word.
                try:
                    second_eq_pos = word.index('=', 1)
                except IndexError:
                    attrs[word[1:]] = ''
                else:
                    attrs[word[1:second_eq_pos]] = word[second_eq_pos + 1:]

            replies.append((reply, attrs))
            if reply == '!done':
                if replies[0][0] == '!trap':
                    raise ApiError(replies[0][1])
                if replies[0][0] == '!fatal':
                    self.sock.close()
                    raise ApiUnrecoverableError(replies[0][1])
                return replies

    def write_sentence(self, words):
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

    def read_sentence(self):
        """
        reads sentence word by word from API socket.

        API uses zero-length word to terminate sentence, so words are read
        until zero-length word is received.

        Returns:
            words - List of API words read from socket
        """
        words = []
        while True:
            word = self.read_word()
            if not word:
                return words
            words.append(word)

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

    def read_word(self):
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
        length = ord(self.read_sock(1))

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
            length += ord(self.read_sock(1))
        # if the three most significant bits are 110
        # -> length is >= 16384, but < 2097152
        elif (length & 0xE0) == 0xC0:
            # unmask and shift the third lowest byte
            length &= ~0xE0
            length <<= 8
            # read and shift second lowest byte
            length += ord(self.read_sock(1))
            length <<= 8
            # read lowest byte
            length += ord(self.read_sock(1))
        # if the four most significant bits are 1110
        # length is >= 2097152, but < 268435456
        elif (length & 0xF0) == 0xE0:
            # unmask and shift the fourth lowest byte
            length &= ~0xF0
            length <<= 8
            # read and shift third lowest byte
            length += ord(self.read_sock(1))
            length <<= 8
            # read and shift second lowest byte
            length += ord(self.read_sock(1))
            length <<= 8
            # read lowest byte
            length += ord(self.read_sock(1))
        # if the five most significant bits are 11110
        # length is >= 268435456, but < 4294967296
        elif (length & 0xF8) == 0xF0:
            # read and shift fourth lowest byte
            length = ord(self.read_sock(1))
            length <<= 8
            # read and shift third lowest byte
            length += ord(self.read_sock(1))
            length <<= 8
            # read and shift second lowest byte
            length += ord(self.read_sock(1))
            length <<= 8
            # read lowest byte
            length += ord(self.read_sock(1))
        else:
            raise ApiUnrecoverableError("unknown control byte received")

        # read actual word from socket, using length determined above
        ret = self.read_sock(length)
        LOG.debug(">>> %s", ret)
        return ret

    def write_sock(self, string):
        """
        write string to API socket, char by char

        Args:
            string - String to send
        """
        for char in string:
            sent_bytes = self.sock.send(bytes(char, 'UTF-8'))
            if not sent_bytes == 1:
                raise ApiUnrecoverableError("could not send to socket")

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
            chunk = self.sock.recv(min(length - len(string), 4096))
            if not chunk:
                raise ApiUnrecoverableError("could not read from socket")
            string = string + chunk.decode('UTF-8', 'replace')
        return string
