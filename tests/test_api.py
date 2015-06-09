from unittest import TestCase
from unittest.mock import Mock
import tikapy


class TestWrites(TestCase):
    """
    Test the write functions.
    """

    WORDS = [
        # word length < 128
        ('', chr(0)),
        ('abc', chr(3) + 'abc'),
        ('12345', chr(5) + '12345'),
        ('b' * 127, chr(127) + ('b' * 127)),
        # word length < 16384
        ('c' * 128, chr(0x80) + chr(128) + ('c' * 128)),
    ]

    def test_write_word(self):
        """
        Call 'write_word' and check what's sent to the socket.
        """
        for inp, out in self.WORDS:
            with self.subTest(size=len(inp), word=inp[:15]):
                sock = Mock()
                api = tikapy.ApiRos(sock)
                sock.send.side_effect = lambda b: len(b)
                api.write_word(inp)
                self.assertEqual(
                    b''.join(c[0][0] for c in sock.sendall.call_args_list),
                    bytes(out, 'latin-1'))
                self.assertLessEqual(sock.sendall.call_count, 5)
