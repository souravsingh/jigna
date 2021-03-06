import os
import sys
import tempfile
import unittest

import mock

from tornado.web import Application
from tornado.httputil import HTTPServerRequest

from jigna.web_server import MainHandler

# A dummy image to write and test with.
DATA = """\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x05\x00\x00\x00\x05\x08\x06\x00\x00\x00\x8do&\xe5\x00\x00\x00\x04gAMA\x00\x00\xb1\x8f\x0b\xfca\x05\x00\x00\x00 cHRM\x00\x00z&\x00\x00\x80\x84\x00\x00\xfa\x00\x00\x00\x80\xe8\x00\x00u0\x00\x00\xea`\x00\x00:\x98\x00\x00\x17p\x9c\xbaQ<\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x01YiTXtXML:com.adobe.xmp\x00\x00\x00\x00\x00<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 5.4.0">\n   <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n      <rdf:Description rdf:about=""\n            xmlns:tiff="http://ns.adobe.com/tiff/1.0/">\n         <tiff:Orientation>1</tiff:Orientation>\n      </rdf:Description>\n   </rdf:RDF>\n</x:xmpmeta>\nL\xc2\'Y\x00\x00\x00tIDAT\x08\x1d\x01i\x00\x96\xff\x01\x00\x1cj\xff}e0\x00;8*\x00\xcb\xcd\xd9\x00\xa2\xad\xd3\x00\x04gP!\x00<9)\x00\x03\x03\x03\x00YVC\x00\xd7\xd9\xe5\x00\x04\x08\x08\x01\x00\xb0\xb4\xc3\x00\n\x08\r\x00\x0f\x0e\x08\x00\xf7\xf8\xfd\x00\x04\xe1\xe3\xf1\x0030\x18\x00\xfc\xfb\x03\x00>>0\x00\x04\x05\x03\x00\x03\xef\xff0\x80\xef\xed\xf3\x00>:$\x00\xdc\xdc\xe5\x00y\x88\xc9\x00\x9a\xa5"\x98\x19\x929\xa9\x00\x00\x00\x00IEND\xaeB`\x82"""


class DummyServer:
    def __init__(self):
        self.html = 'html'
        self.base_url = '/'


class TestableMainHandler(MainHandler):
    def write(self, data):
        self.test_data = data


class TestMainHandler(unittest.TestCase):

    def setUp(self):
        self.tmpfile = ''
        self.fd = None

    def tearDown(self):
        if len(self.tmpfile) > 0 and os.path.exists(self.tmpfile):
            os.close(self.fd)
            os.remove(self.tmpfile)

    def _make_text_data(self):
        self.fd, self.tmpfile = tempfile.mkstemp('.txt')
        with open(self.tmpfile, 'w') as fp:
            fp.write('hello')

    def _make_binary_data(self):
        self.fd, self.tmpfile = tempfile.mkstemp('.png')
        with open(self.tmpfile, 'wb') as fp:
            fp.write(DATA)

    def _make_request(self, path):
        request = mock.MagicMock(spec=HTTPServerRequest)()
        if sys.platform.startswith('win'):
            request.path = '/' + path
        else:
            request.path = path
        return request

    def test_get_root(self):
        # Given
        request = self._make_request('')
        app = Application()
        server = DummyServer()

        # When
        h = TestableMainHandler(app, request, server=server)
        h.get()

        # Then
        self.assertEqual(h.test_data, 'html')

    def test_get_text_data(self):
        # Given
        self._make_text_data()
        request = self._make_request(self.tmpfile)
        app = Application()
        server = DummyServer()

        # When
        h = TestableMainHandler(app, request, server=server)
        h.get()

        # Then
        self.assertEqual(h.test_data, 'hello')

    def test_get_binary_data(self):
        # Given
        self._make_binary_data()
        request = self._make_request(self.tmpfile)
        app = Application()
        server = DummyServer()

        # When
        h = TestableMainHandler(app, request, server=server)
        h.get()

        # Then
        self.assertEqual(h.test_data, DATA)


if __name__ == '__main__':
    unittest.main()
