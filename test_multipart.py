# -*- coding: utf-8 -*-
import unittest
import sys, os.path
from multipart import *

#TODO: bufsize=10, line=1234567890--boundary\n
#TODO: bufsize < len(boundary) (should not be possible)
#TODO: bufsize = len(boundary)+5 (edge case)
#TODO: At least one test per possible exception (100% coverage)

class TestHeaderParser(unittest.TestCase):

    def test_token_unquote(self):
        unquote = header_unquote
        self.assertEqual('foo', unquote('"foo"'))
        self.assertEqual('foo"bar', unquote('"foo\\"bar"'))
        self.assertEqual('ie.exe', unquote('"\\\\network\\ie.exe"', True))
        self.assertEqual('ie.exe', unquote('"c:\\wondows\\ie.exe"', True))

    def test_options_parser(self):
        parse = parse_options_header
        head = 'form-data; name="Test"; '
        self.assertEqual(parse(head+'filename="Test.txt"')[0], 'form-data')
        self.assertEqual(parse(head+'filename="Test.txt"')[1]['name'], 'Test')
        self.assertEqual(parse(head+'filename="Test.txt"')[1]['filename'], 'Test.txt')
        self.assertEqual(parse(head+'FileName="Test.txt"')[1]['filename'], 'Test.txt')
        self.assertEqual(parse(head+'filename="C:\\test\\bla.txt"')[1]['filename'], 'bla.txt')
        self.assertEqual(parse(head+'filename="\\\\test\\bla.txt"')[1]['filename'], 'bla.txt')

    def test_line_parser(self):
        for line in ('foo',''):
            for ending in ('\n','\r\n'):
                i = MultipartParser(io.BytesIO(line+ending), 'foo')
                i = i._lineiter().next()
                self.assertEqual(i, (line, ending))

    def test_iterlines(self):
        data = 'abc\ndef\r\nghi'
        result = [('abc','\n'),('def','\r\n'),('ghi','')]
        i = MultipartParser(io.BytesIO(data), 'foo')._lineiter()
        self.assertEqual(list(i), result)
    
    def test_iterlines_limit(self):
        data, limit = 'abc\ndef\r\nghi', 10
        result = [('abc','\n'),('def','\r\n'),('g','')]
        i = MultipartParser(io.BytesIO(data), 'foo', limit)._lineiter()
        self.assertEqual(list(i), result)
        data, limit = 'abc\ndef\r\nghi', 8
        result = [('abc','\n'),('def\r','')]
        i = MultipartParser(io.BytesIO(data), 'foo', limit)._lineiter()
        self.assertEqual(list(i), result)

    def test_iterlines_maxbuf(self):
        data, limit = ('X'*3*1024)+'x\n', 1024
        result = [('X'*1024,''),('X'*1024,''),('X'*1024,''),('x','\n')]
        i = MultipartParser(io.BytesIO(data), 'foo', buffer_size=limit)._lineiter()
        self.assertEqual(list(i), result)

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

    def test_multipart(self):
        """Tests multipart parsing against data collected from webbrowsers"""
        resources = os.path.join(os.path.dirname(__file__), 'multipart')
        repository = [
            ('firefox3-2png1txt', '---------------------------186454651713519341951581030105', [
                (u'anchor.png', 'file1', 'image/png', 'file1.png'),
                (u'application_edit.png', 'file2', 'image/png', 'file2.png')
            ], u'example text'),
            ('firefox3-2pnglongtext', '---------------------------14904044739787191031754711748', [
                (u'accept.png', 'file1', 'image/png', 'file1.png'),
                (u'add.png', 'file2', 'image/png', 'file2.png')
            ], u'--long text\r\n--with boundary\r\n--lookalikes--'),
            ('opera8-2png1txt', '----------zEO9jQKmLc2Cq88c23Dx19', [
                (u'arrow_branch.png', 'file1', 'image/png', 'file1.png'),
                (u'award_star_bronze_1.png', 'file2', 'image/png', 'file2.png')
            ], u'blafasel öäü'),
            ('webkit3-2png1txt', '----WebKitFormBoundaryjdSFhcARk8fyGNy6', [
                (u'gtk-apply.png', 'file1', 'image/png', 'file1.png'),
                (u'gtk-no.png', 'file2', 'image/png', 'file2.png')
            ], u'this is another text with ümläüts'),
            ('ie6-2png1txt', '---------------------------7d91b03a20128', [
                (u'file1.png', 'file1', 'image/x-png', 'file1.png'),
                (u'file2.png', 'file2', 'image/x-png', 'file2.png')
            ], u'ie6 sucks :-/')
        ]

        for name, boundary, files, text in repository:
            folder = os.path.join(resources, name)
            env = {'REQUEST_METHOD': 'POST',
                   'CONTENT_TYPE': 'multipart/form-data; boundary=%s'%boundary}
            with open(os.path.join(folder, 'request.txt'), 'rb') as fp:
                env['wsgi.input'] = fp
                rforms, rfiles = parse_form_data(env, strict=True)
                for filename, field, content_type, fsname in files:
                    data = open(os.path.join(folder, fsname), 'rb').read()
                    self.assertEqual(rfiles[field].name, field)
                    self.assertEqual(rfiles[field].filename, filename)
                    self.assertEqual(rfiles[field].content_type, content_type)
                    self.assertEqual(rfiles[field].value, data)
                self.assertEqual(rforms['text'], text)

