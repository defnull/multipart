# -*- coding: utf-8 -*-
import unittest
import sys, os.path
import multipart

class TestHeaderParser(unittest.TestCase):

    def test_token_unquote(self):
        unquote = multipart.header_unquote
        self.assertEqual('foo', unquote('"foo"'))
        self.assertEqual('foo"bar', unquote('"foo\\"bar"'))
        self.assertEqual('ie.exe', unquote('"\\\\network\\ie.exe"', True))
        self.assertEqual('ie.exe', unquote('"c:\\wondows\\ie.exe"', True))

    def test_options_parser(self):
        parse = multipart.parse_options_header
        head = 'form-data; name="Test"; '
        self.assertEqual(parse(head+'filename="Test.txt"')[0], 'form-data')
        self.assertEqual(parse(head+'filename="Test.txt"')[1]['name'], 'Test')
        self.assertEqual(parse(head+'filename="Test.txt"')[1]['filename'], 'Test.txt')
        self.assertEqual(parse(head+'FileName="Test.txt"')[1]['filename'], 'Test.txt')
        self.assertEqual(parse(head+'filename="C:\\test\\bla.txt"')[1]['filename'], 'bla.txt')
        self.assertEqual(parse(head+'filename="\\\\test\\bla.txt"')[1]['filename'], 'bla.txt')

    def test_line_parser(self):
        parse = multipart.parse_line
        for line in ('foo',''):
            for ending in ('\n','\r','\n\r'):
                self.assertEqual(parse(line+ending), (line, ending))

    def test_iterlines(self):
        iterlines = multipart.iterlines
        data = 'abc\ndef\r\nghi\rfoo'
        self.assertEqual(list(iterlines(io.BytesIO(data))), data.splitlines(True))
    
    def test_iterlines_limit(self)
        iterlines = multipart.iterlines
        data = 'abc\ndef\r\nghi\rfoo'
        ldata = data[:11]
        self.assertEqual(list(iterlines(io.BytesIO(data), 11)), ldata.splitlines(True))

    def test_iterlines_maxbuf(self)
        iterlines = multipart.iterlines
        MAXBUF = multipart.MAXBUF
        t = iterlines(io.BytesIO(('abc'*MAXBUF)+'x\n'))
        self.assertEqual(len(t.next()), MAXBUF)
        self.assertEqual(len(t.next()), MAXBUF)
        self.assertEqual(len(t.next()), MAXBUF)
        self.assertEqual(t.next(), 'x\n')

    def test_copyfile(self):
        source = io.BytesIO('abc')
        target = io.BytesIO()
        self.assertEqual(copy_file(source, target), 3)
        target.seek(0)
        self.assertEqual(target.read(), 'abc')

class TestMultipartParser(unittest.TestCase):
    def setUp(self):
        self.env = {'REQUEST_METHOD':'POST',
                    'CONTENT_TYPE':'multipart/form-data; boundary=foo',
                    'wsgi.input': io.BytesIO()}

