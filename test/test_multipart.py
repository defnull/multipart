# -*- coding: utf-8 -*-
import unittest
import base64
import os.path, tempfile

from io import BytesIO

import multipart as mp
from multipart import to_bytes

#TODO: bufsize=10, line=1234567890--boundary\n
#TODO: bufsize < len(boundary) (should not be possible)
#TODO: bufsize = len(boundary)+5 (edge case)
#TODO: At least one test per possible exception (100% coverage)


class TestHeaderParser(unittest.TestCase):

    def test_token_unquote(self):
        unquote = mp.header_unquote
        self.assertEqual('foo', unquote('"foo"'))
        self.assertEqual('foo"bar', unquote('"foo\\"bar"'))
        self.assertEqual('ie.exe', unquote('"\\\\network\\ie.exe"', True))
        self.assertEqual('ie.exe', unquote('"c:\\wondows\\ie.exe"', True))

    def test_token_quote(self):
        quote = mp.header_quote
        self.assertEqual(quote('foo'), 'foo')
        self.assertEqual(quote('foo"bar'), '"foo\\"bar"')

    def test_options_parser(self):
        parse = mp.parse_options_header
        head = 'form-data; name="Test"; '
        self.assertEqual(parse(head+'filename="Test.txt"')[0], 'form-data')
        self.assertEqual(parse(head+'filename="Test.txt"')[1]['name'], 'Test')
        self.assertEqual(parse(head+'filename="Test.txt"')[1]['filename'], 'Test.txt')
        self.assertEqual(parse(head+'FileName="Te\\"st.txt"')[1]['filename'], 'Te"st.txt')
        self.assertEqual(parse(head+'filename="C:\\test\\bla.txt"')[1]['filename'], 'bla.txt')
        self.assertEqual(parse(head+'filename="\\\\test\\bla.txt"')[1]['filename'], 'bla.txt')


class TestMultipartParser(unittest.TestCase):

    def test_copyfile(self):
        source = BytesIO(to_bytes('abc'))
        target = BytesIO()
        self.assertEqual(mp.copy_file(source, target), 3)
        target.seek(0)
        self.assertEqual(target.read(), to_bytes('abc'))

    def test_big_file(self):
        ''' If the size of an uploaded part exceeds memfile_limit,
            it is written to disk. '''
        test_file = 'abc'*1024
        boundary = '---------------------------186454651713519341951581030105'
        request = BytesIO(to_bytes('\r\n').join(map(to_bytes,[
        '--' + boundary,
        'Content-Disposition: form-data; name="file1"; filename="random.png"',
        'Content-Type: image/png', '', test_file, '--' + boundary,
        'Content-Disposition: form-data; name="file2"; filename="random.png"',
        'Content-Type: image/png', '', test_file + 'a', '--' + boundary,
        'Content-Disposition: form-data; name="file3"; filename="random.png"',
        'Content-Type: image/png', '', test_file*2, '--'+boundary+'--',''])))
        p = mp.MultipartParser(request, boundary, memfile_limit=len(test_file))
        try:
            self.assertEqual(p.get('file1').file.read(), to_bytes(test_file))
            self.assertTrue(p.get('file1').is_buffered())
            self.assertEqual(p.get('file2').file.read(), to_bytes(test_file + 'a'))
            self.assertFalse(p.get('file2').is_buffered())
            self.assertEqual(p.get('file3').file.read(), to_bytes(test_file*2))
            self.assertFalse(p.get('file3').is_buffered())
        finally:
            for part in p:
                part.close()

    def test_get_all(self):
        ''' Test the get() and get_all() methods. '''
        boundary = '---------------------------186454651713519341951581030105'
        request = BytesIO(to_bytes('\r\n').join(map(to_bytes,[
        '--' + boundary,
        'Content-Disposition: form-data; name="file1"; filename="random.png"',
        'Content-Type: image/png', '', 'abc'*1024, '--' + boundary,
        'Content-Disposition: form-data; name="file1"; filename="random.png"',
        'Content-Type: image/png', '', 'def'*1024, '--' + boundary + '--',''])))
        p = mp.MultipartParser(request, boundary)
        self.assertEqual(p.get('file1').file.read(), to_bytes('abc'*1024))
        self.assertEqual(p.get('file2'), None)
        self.assertEqual(len(p.get_all('file1')), 2)
        self.assertEqual(p.get_all('file1')[1].file.read(), to_bytes('def'*1024))
        self.assertEqual(p.get_all('file1'), p.parts())

    def test_file_seek(self):
        ''' The file object should be readable withoud a seek(0). '''
        test_file = 'abc'*1024
        boundary = '---------------------------186454651713519341951581030105'
        request = BytesIO(to_bytes('\r\n').join(map(to_bytes,[
        '--' + boundary,
        'Content-Disposition: form-data; name="file1"; filename="random.png"',
        'Content-Type: image/png', '', test_file, '--' + boundary + '--',''])))
        p = mp.MultipartParser(request, boundary)
        self.assertEqual(p.get('file1').file.read(), to_bytes(test_file))
        self.assertEqual(p.get('file1').value, test_file)

    def test_unicode_value(self):
        ''' The .value property always returns unicode '''
        test_file = 'abc'*1024
        boundary = '---------------------------186454651713519341951581030105'
        request = BytesIO(to_bytes('\r\n').join(map(to_bytes,[
        '--' + boundary,
        'Content-Disposition: form-data; name="file1"; filename="random.png"',
        'Content-Type: image/png', '', test_file, '--' + boundary + '--',''])))
        p = mp.MultipartParser(request, boundary)
        self.assertEqual(p.get('file1').file.read(), to_bytes(test_file))
        self.assertEqual(p.get('file1').value, test_file)
        self.assertTrue(hasattr(p.get('file1').value, 'encode'))

    def test_save_as(self):
        ''' save_as stores data in a file keeping the file position. '''
        def tmp_file_name():
            # create a temporary file name (on Python 2.6+ NamedTemporaryFile
            # with delete=False could be used)
            fd, fname = tempfile.mkstemp()
            f = os.fdopen(fd)
            f.close()
            return fname
        test_file = 'abc'*1024
        boundary = '---------------------------186454651713519341951581030105'
        request = BytesIO(to_bytes('\r\n').join(map(to_bytes,[
        '--' + boundary,
        'Content-Disposition: form-data; name="file1"; filename="random.png"',
        'Content-Type: image/png', '', test_file, '--' + boundary + '--',''])))
        p = mp.MultipartParser(request, boundary)
        self.assertEqual(p.get('file1').file.read(1024), to_bytes(test_file)[:1024])
        tfn = tmp_file_name()
        p.get('file1').save_as(tfn)
        tf = open(tfn, 'rb')
        self.assertEqual(tf.read(), to_bytes(test_file))
        tf.close()
        self.assertEqual(p.get('file1').file.read(), to_bytes(test_file)[1024:])

    def test_multiline_header(self):
        ''' HTTP allows headers to be multiline. '''
        test_file = to_bytes('abc'*1024)
        test_text = u'Test text\n with\r\n ümläuts!'
        boundary = '---------------------------186454651713519341951581030105'
        request = BytesIO(to_bytes('\r\n').join(map(to_bytes,[
        '--' + boundary,
        'Content-Disposition: form-data;',
        '\tname="file1"; filename="random.png"',
        'Content-Type: image/png', '', test_file, '--' + boundary,
        'Content-Disposition: form-data;',
        ' name="text"', '', test_text,
        '--' + boundary + '--',''])))
        p = mp.MultipartParser(request, boundary, charset='utf8')
        self.assertEqual(p.get('file1').file.read(), test_file)
        self.assertEqual(p.get('file1').filename, 'random.png')
        self.assertEqual(p.get('text').value, test_text)


class TestFormParser(unittest.TestCase):
    def setUp(self):
        self.data = BytesIO()
        self.env = {'REQUEST_METHOD':'POST',
                    'CONTENT_TYPE':'multipart/form-data; boundary=foo',
                    'wsgi.input': self.data}

    def write(self, *lines):
        for line in lines:
            self.data.write(to_bytes(line))

    def parse(self, *lines, **kwargs):
        self.write(*lines)
        self.data.seek(0)
        kwargs['environ'] = self.env
        kwargs['strict'] = True
        kwargs.setdefault('charset', 'utf8')
        return mp.parse_form_data(**kwargs)

    def test_multipart(self):
       forms, files = self.parse('--foo\r\n',
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc\r\n', '--foo\r\n',
                   'Content-Disposition: form-data; name="text1"\r\n', '\r\n',
                   'abc\r\n', '--foo--')
       self.assertEqual(forms['text1'], 'abc')
       self.assertEqual(files['file1'].file.read(), to_bytes('abc'))
       self.assertEqual(files['file1'].filename, 'random.png')
       self.assertEqual(files['file1'].name, 'file1')
       self.assertEqual(files['file1'].content_type, 'image/png')

    def test_empty(self):
        forms, files = self.parse('--foo--\r\n')
        self.assertEqual(0, len(forms))
        self.assertEqual(0, len(files))

    def test_urlencoded(self):
        for ctype in ('application/x-www-form-urlencoded', 'application/x-url-encoded'):
            self.env['CONTENT_TYPE'] = ctype
            forms, files = self.parse('a=b&c=d')
            self.assertEqual(forms['a'], 'b')
            self.assertEqual(forms['c'], 'd')

    def test_urlencoded_latin1(self):
        for ctype in ('application/x-www-form-urlencoded', 'application/x-url-encoded'):
            self.env['CONTENT_TYPE'] = ctype
            forms, files = self.parse(b'a=\xe0\xe1&e=%E8%E9', charset='iso-8859-1')
            self.assertEqual(forms['a'], 'àá')
            self.assertEqual(forms['e'], 'èé')

    def test_urlencoded_utf8(self):
        for ctype in ('application/x-www-form-urlencoded', 'application/x-url-encoded'):
            self.env['CONTENT_TYPE'] = ctype
            forms, files = self.parse(b'a=\xc6\x80\xe2\x99\xad&e=%E1%B8%9F%E2%99%AE')
            self.assertEqual(forms['a'], 'ƀ♭')
            self.assertEqual(forms['e'], 'ḟ♮')


class TestBrokenMultipart(unittest.TestCase):
    def setUp(self):
        self.data = BytesIO()
        self.env = {'REQUEST_METHOD':'POST',
                    'CONTENT_TYPE':'multipart/form-data; boundary=foo',
                    'wsgi.input': self.data}

    def write(self, *lines):
        self.data.truncate(0)
        for line in lines:
            self.data.write(to_bytes(line))

    def parse(self, *lines, **kwargs):
        self.write(*lines)
        self.data.seek(0)
        kwargs['environ'] = self.env
        kwargs['strict'] = True
        kwargs['charset'] = 'utf8'
        return mp.parse_form_data(**kwargs)

    def assertMPError(self, *a, **ka):
        self.data.seek(0)
        ka['environ'] = self.env
        ka['strict'] = True
        ka['charset'] = 'utf8'
        self.assertRaises(mp.MultipartError, mp.parse_form_data, **ka)
        ka['strict'] = False
        self.data.seek(0)
        self.assertTrue(mp.parse_form_data(**ka))

    def test_empty(self):
        self.assertMPError()

    def test_big_boundary(self):
        self.env['CONTENT_TYPE'] = 'multipart/form-data; boundary='+'foo'*1024
        self.assertMPError(buffer_size=1024*3)

    def test_wrong_method(self):
        self.env['REQUEST_METHOD'] = 'GET'
        self.assertMPError()

    def test_missing_content_type(self):
        del self.env['CONTENT_TYPE']
        self.assertMPError()

    def test_unsupported_content_type(self):
        self.env['CONTENT_TYPE'] = 'multipart/fantasy'
        self.assertMPError()

    def test_missing_boundary(self):
        self.env['CONTENT_TYPE'] = 'multipart/form-data'
        self.assertMPError()

    def test_invalid_content_length(self):
        self.env['CONTENT_LENGTH'] = ''
        self.assertMPError()
        self.env['CONTENT_LENGTH'] = 'notanumber'
        self.assertMPError()

    def test_invalid_environ(self):
        del self.env['wsgi.input']
        self.assertMPError()

    def test_part_ends_after_header(self):
        self.write('--foo\r\n', 'Header: value\r\n', '--foo--')
        self.assertMPError()

    def test_part_ends_in_header(self):
        self.write('--foo\r\n', 'Header: value', '--foo--')
        self.assertMPError()

    def test_no_terminator(self):
        self.write('--foo\r\n',
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc')
        self.assertMPError()

    def test_no_newline_after_content(self):
        self.write('--foo\r\n',
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc', '--foo--')
        self.assertMPError()

    def test_no_newline_after_middle_content(self):
        forms, files = self.parse('--foo\r\n',
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc', '--foo\r\n'
                   'Content-Disposition: form-data; name="file2"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc\r\n', '--foo--')
        self.assertEqual(len(files), 1)
        self.assertTrue(to_bytes('name="file2"') in files['file1'].file.read())

    def test_ignore_junk_before_start_boundary(self):
        forms, files = self.parse('Preamble\r\n', '--foo\r\n'
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc\r\n', '--foo--')
        self.assertEqual(files['file1'].file.read(), to_bytes('abc'))
        self.assertEqual(files['file1'].filename, 'random.png')
        self.assertEqual(files['file1'].name, 'file1')
        self.assertEqual(files['file1'].content_type, 'image/png')

    def test_allow_junk_after_end_boundary(self):
        self.parse('--foo--\r\njunk')
        self.parse('--foo\r\n'
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc\r\n', '--foo--\r\n', 'junk') 

    def test_no_start_boundary(self):
        self.write('--bar\r\n','--nonsense\r\n'
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc\r\n', '--nonsense--')
        self.assertMPError()

    def test_no_end_boundary(self):
        self.write('--foo\r\n',
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc\r\n')
        self.assertMPError()

    def test_just_end_boundary(self):
        files, forms = self.parse('--foo--') # is fine
        self.assertTrue(not files)
        self.assertTrue(not forms)

    def test_empty_part(self):
        self.write('--foo\r\n', '--foo--')
        self.assertMPError()

    def test_disk_limit(self):
        self.write('--foo\r\n',
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc'*1024+'\r\n', '--foo--')
        self.assertMPError(memfile_limit=1, disk_limit=1024)

    def test_mem_limit(self):
        self.write('--foo\r\n',
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc'*1024+'\r\n', '--foo\r\n',
                   'Content-Disposition: form-data; name="file2"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc'*1024+'\r\n', '--foo--')
        self.assertMPError(mem_limit=1024*3)

    def test_invalid_header(self):
        self.write('--foo\r\n',
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n',
                   'Bad header\r\n', '\r\n', 'abc'*1024+'\r\n', '--foo--')
        self.assertMPError()

    def test_content_length_to_small(self):
        self.write('--foo\r\n',
                   'Content-Disposition: form-data; name="file1"; filename="random.png"\r\n',
                   'Content-Type: image/png\r\n',
                   'Content-Length: 111\r\n', '\r\n', 'abc'*1024+'\r\n', '--foo--')
        self.assertMPError()

    def test_no_disposition_header(self):
        self.write('--foo\r\n',
                   'Content-Type: image/png\r\n', '\r\n', 'abc'*1024+'\r\n', '--foo--')
        self.assertMPError()

    def test_big_urlencoded_detect_early(self):
       self.env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
       self.env['CONTENT_LENGTH'] = 1024+2
       self.write('a='+'b'*1024)
       self.assertMPError(mem_limit=1024)

    def test_big_urlencoded_detect_late(self):
       self.env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
       self.write('a='+'b'*1024)
       self.assertMPError(mem_limit=1024)


''' The files used by the following test were taken from the werkzeug library
    test suite and are therefore partly copyrighted by the Werkzeug Team
    under BSD licence. See https://werkzeug.palletsprojects.com/ '''

browser_test_cases = {}
browser_test_cases['firefox3-2png1txt'] = {'data': base64.b64decode(to_bytes('''
LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0xODY0NTQ2NTE3MTM1MTkzNDE5NTE1ODEwMzAx
MDUNCkNvbnRlbnQtRGlzcG9zaXRpb246IGZvcm0tZGF0YTsgbmFtZT0iZmlsZTEiOyBmaWxlbmFt
ZT0iYW5jaG9yLnBuZyINCkNvbnRlbnQtVHlwZTogaW1hZ2UvcG5nDQoNColQTkcNChoKAAAADUlI
RFIAAAAQAAAAEAgGAAAAH/P/YQAAAARnQU1BAACvyDcFiukAAAAZdEVYdFNvZnR3YXJlAEFkb2Jl
IEltYWdlUmVhZHlxyWU8AAABnUlEQVQ4y6VTMWvCQBS+qwEFB10KGaS1P6FDpw7SrVvzAwRRx04V
Ck4K6iAoDhLXdhFcW9qhZCk4FQoW0gp2U4lQRDAUS4hJmn5Xgg2lsQ198PHu3b3vu5d3L9S2bfIf
47wOer1ewzTNtGEYBP48kUjkfsrb8BIAMb1cLovwRfi07wrYzcCr4/1/Am4FzzhzBGZeefR7E7vd
7j0Iu4wYjUYDBMfD0dBiMUQfstns3toKkHgF6EgmqqruW6bFiHcsxr70awVu63Q6NiOmUinquwfM
dF1f28CVgCRJx0jMAQ1BEFquRn7CbYVCYZVbr9dbnJMohoIh9kViu90WEW9nMpmxu4JyubyF/VEs
FiNcgCPyoyxiu7XhCPBzdU4s652VnUccbDabPLyN2C6VSmwdhFgel5DB84AJb64mEUlvmqadTKcv
40gkUkUsg1DjeZ7iRsrWgByP71T7/afxYrHIYry/eoBD9mxsaK4VRamFw2EBQknMAWGvRClNTpQJ
AfkCxFNgBmiez1ipVA4hdgQcOD/TLfylKIo3vubgL/YBnIw+ioOMLtwAAAAASUVORK5CYIINCi0t
LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tMTg2NDU0NjUxNzEzNTE5MzQxOTUxNTgxMDMwMTA1
DQpDb250ZW50LURpc3Bvc2l0aW9uOiBmb3JtLWRhdGE7IG5hbWU9ImZpbGUyIjsgZmlsZW5hbWU9
ImFwcGxpY2F0aW9uX2VkaXQucG5nIg0KQ29udGVudC1UeXBlOiBpbWFnZS9wbmcNCg0KiVBORw0K
GgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0U29mdHdh
cmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJRSURBVBgZpcHda81xHMDx9+d3fudYzuYw2RaZ5yTW
olEiuZpCSjGJFEktUUr8A6ZxQZGHmDtqdrGUXHgoeZqSp1F2bLFWjtkOB8PZzvmd7+djv5XaBRfL
6yVmxv+QjQeu7l25uuZYJmtxM0AVU8Wpw9RQU8w51AxzDqfKhFjwq6Mjdbj1RN0Zv2ZFzaloUdwr
L2Is4r+y7hRwxs8G5mUzPxmrwcA8hvnmjIZtcxmr3Y09hHwzJZQvOAwwNZyCYqgaThVXMFzBCD7f
Jfv8MpHiKvaV3ePV2f07fMwIiSeIGeYJJoao4HmCiIeIQzPXifY+paJqO4lZi/nWPZ/krabjvlNH
yANMBAQiBiqgakQMCunbxHJviM9bQeZdBzHJUzKhguLJlQnf1BghAmZ4gImAgAjk++8jP56QmL2G
XG8zsfFCz8skA1mQXKbaU3X8ISIgQsgDcun7FL7cJjFnLUMfLyLRr0SLS4hbhiup5Szd19rpFYKA
ESKICCERoS95neyHmyTmbmAodQ4vGpAfmEn6YTtTahv4ODiRkGdOCUUAAUSE/uQNfqTaKFu4jvyn
JiIxIzcwg/SjF1RsOk9R+QJMlZCvqvwhQFdbM4XvrynIVHpfn2ZSWYyhzHS+PUtSueUC0cQ0QmpG
yE9197TUnwzq1DnUKbXSxOb6S7xtPkjngzbGVVbzvS/FjaGt9DU8xlRRJdTCMDEzRjuyZ1FwaFe9
j+d4eecaPd1dPxNTSlfWHm1v5y/EzBitblXp4JLZ5f6yBbOwaK5tsD+9c33jq/f8w2+mRSjOllPh
kAAAAABJRU5ErkJggg0KLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0xODY0NTQ2NTE3MTM1
MTkzNDE5NTE1ODEwMzAxMDUNCkNvbnRlbnQtRGlzcG9zaXRpb246IGZvcm0tZGF0YTsgbmFtZT0i
dGV4dCINCg0KZXhhbXBsZSB0ZXh0DQotLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLTE4NjQ1
NDY1MTcxMzUxOTM0MTk1MTU4MTAzMDEwNS0tDQo=''')),
'boundary':'---------------------------186454651713519341951581030105',
'files': {'file1': (u'anchor.png', 'image/png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0
U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAGdSURBVDjLpVMxa8JAFL6rAQUHXQoZpLU/
oUOnDtKtW/MDBFHHThUKTgrqICgOEtd2EVxb2qFkKTgVChbSCnZTiVBEMBRLiEmafleCDaWxDX3w
8e7dve+7l3cv1LZt8h/jvA56vV7DNM20YRgE/jyRSOR+ytvwEgAxvVwui/BF+LTvCtjNwKvj/X8C
bgXPOHMEZl559HsTu93uPQi7jBiNRgMEx8PR0GIxRB+y2eze2gqQeAXoSCaqqu5bpsWIdyzGvvRr
BW7rdDo2I6ZSKeq7B8x0XV/bwJWAJEnHSMwBDUEQWq5GfsJthUJhlVuv11uckyiGgiH2RWK73RYR
b2cymbG7gnK5vIX9USwWI1yAI/KjLGK7teEI8HN1TizrnZWdRxxsNps8vI3YLpVKbB2EWB6XkMHz
gAlvriYRSW+app1Mpy/jSCRSRSyDUON5nuJGytaAHI/vVPv9p/FischivL96gEP2bGxorhVFqYXD
YQFCScwBYa9EKU1OlAkB+QLEU2AGaJ7PWKlUDiF2BBw4P9Mt/KUoije+5uAv9gGcjD6Kg4wu3AAA
AABJRU5ErkJggg=='''))),
          'file2': (u'application_edit.png', 'image/png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0
U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJRSURBVBgZpcHda81xHMDx9+d3fudYzuYw
2RaZ5yTWolEiuZpCSjGJFEktUUr8A6ZxQZGHmDtqdrGUXHgoeZqSp1F2bLFWjtkOB8PZzvmd7+dj
v5XaBRfL6yVmxv+QjQeu7l25uuZYJmtxM0AVU8Wpw9RQU8w51AxzDqfKhFjwq6Mjdbj1RN0Zv2ZF
zaloUdwrL2Is4r+y7hRwxs8G5mUzPxmrwcA8hvnmjIZtcxmr3Y09hHwzJZQvOAwwNZyCYqgaThVX
MFzBCD7fJfv8MpHiKvaV3ePV2f07fMwIiSeIGeYJJoao4HmCiIeIQzPXifY+paJqO4lZi/nWPZ/k
rabjvlNHyANMBAQiBiqgakQMCunbxHJviM9bQeZdBzHJUzKhguLJlQnf1BghAmZ4gImAgAjk++8j
P56QmL2GXG8zsfFCz8skA1mQXKbaU3X8ISIgQsgDcun7FL7cJjFnLUMfLyLRr0SLS4hbhiup5Szd
19rpFYKAESKICCERoS95neyHmyTmbmAodQ4vGpAfmEn6YTtTahv4ODiRkGdOCUUAAUSE/uQNfqTa
KFu4jvynJiIxIzcwg/SjF1RsOk9R+QJMlZCvqvwhQFdbM4XvrynIVHpfn2ZSWYyhzHS+PUtSueUC
0cQ0QmpGyE9197TUnwzq1DnUKbXSxOb6S7xtPkjngzbGVVbzvS/FjaGt9DU8xlRRJdTCMDEzRjuy
Z1FwaFe9j+d4eecaPd1dPxNTSlfWHm1v5y/EzBitblXp4JLZ5f6yBbOwaK5tsD+9c33jq/f8w2+m
RSjOllPhkAAAAABJRU5ErkJggg==''')))},
'forms': {'text': u'example text'}}

browser_test_cases['firefox3-2pnglongtext'] = {'data': base64.b64decode(to_bytes('''
LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0xNDkwNDA0NDczOTc4NzE5MTAzMTc1NDcxMTc0
OA0KQ29udGVudC1EaXNwb3NpdGlvbjogZm9ybS1kYXRhOyBuYW1lPSJmaWxlMSI7IGZpbGVuYW1l
PSJhY2NlcHQucG5nIg0KQ29udGVudC1UeXBlOiBpbWFnZS9wbmcNCg0KiVBORw0KGgoAAAANSUhE
UgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0U29mdHdhcmUAQWRvYmUg
SW1hZ2VSZWFkeXHJZTwAAAKfSURBVDjLpZPrS1NhHMf9O3bOdmwDCWREIYKEUHsVJBI7mg3FvCxL
09290jZj2EyLMnJexkgpLbPUanNOberU5taUMnHZUULMvelCtWF0sW/n7MVMEiN64AsPD8/n83uu
cQDi/id/DBT4Dolypw/qsz0pTMbj/WHpiDgsdSUyUmeiPt2+V7SrIM+bSss8ySGdR4abQQv6lrui
6VxsRonrGCS9VEjSQ9E7CtiqdOZ4UuTqnBHO1X7YXl6Daa4yGq7vWO1D40wVDtj4kWQbn94myPGk
CDPdSesczE2sCZShwl8CzcwZ6NiUs6n2nYX99T1cnKqA2EKui6+TwphA5k4yqMayopU5mANV3lNQ
TBdCMVUA9VQh3GuDMHiVcLCS3J4jSLhCGmKCjBEx0xlshjXYhApfMZRP5CyYD+UkG08+xt+4wLVQ
ZA1tzxthm2tEfD3JxARH7QkbD1ZuozaggdZbxK5kAIsf5qGaKMTY2lAU/rH5HW3PLsEwUYy+YCcE
RmIjJpDcpzb6l7th9KtQ69fi09ePUej9l7cx2DJbD7UrG3r3afQHOyCo+V3QQzE35pvQvnAZukk5
zL5qRL59jsKbPzdheXoBZc4saFhBS6AO7V4zqCpiawuptwQG+UAa7Ct3UT0hh9p9EnXT5Vh6t4C2
2QaUDh6HwnECOmcO7K+6kW49DKqS2DrEZCtfuI+9GrNHg4fMHVSO5kE7nAPVkAxKBxcOzsajpS4Y
h4ohUPPWKTUh3PaQEptIOr6BiJjcZXCwktaAGfrRIpwblqOV3YKdhfXOIvBLeREWpnd8ynsaSJoy
ESFphwTtfjN6X1jRO2+FxWtCWksqBApeiFIR9K6fiTpPiigDoadqCEag5YUFKl6Yrciw0VOlhOiv
v/Ff8wtn0KzlebrUYwAAAABJRU5ErkJggg0KLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0x
NDkwNDA0NDczOTc4NzE5MTAzMTc1NDcxMTc0OA0KQ29udGVudC1EaXNwb3NpdGlvbjogZm9ybS1k
YXRhOyBuYW1lPSJmaWxlMiI7IGZpbGVuYW1lPSJhZGQucG5nIg0KQ29udGVudC1UeXBlOiBpbWFn
ZS9wbmcNCg0KiVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK
6QAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJvSURBVDjLpZPrS5NhGIf9
W7YvBYOkhlkoqCklWChv2WyKik7blnNris72bi6dus0DLZ0TDxW1odtopDs4D8MDZuLU0kXq61Ci
jSIIasOvv94VTUfLiB74fXngup7nvrnvJABJ/5PfLnTTdcwOj4RsdYmo5glBWP6iOtzwvIKSWstI
0Wgx80SBblpKtE9KQs/We7EaWoT/8wbWP61gMmCH0lMDvokT4j25TiQU/ITFkek9Ow6+7WH2gwsm
ahCPdwyw75uw9HEO2gUZSkfyI9zBPCJOoJ2SMmg46N61YO/rNoa39Xi41oFuXysMfh36/Fp0b7bA
fWAH6RGi0HglWNCbzYgJaFjRv6zGuy+b9It96N3SQvNKiV9HvSaDfFEIxXItnPs23BzJQd6DDEVM
0OKsoVwBG/1VMzpXVWhbkUM2K4oJBDYuGmbKIJ0qxsAbHfRLzbjcnUbFBIpx/qH3vQv9b3U03IQ/
HfFkERTzfFj8w8jSpR7GBE123uFEYAzaDRIqX/2JAtJbDat/COkd7CNBva2cMvq0MGxp0PRSCPF8
BXjWG3FgNHc9XPT71Ojy3sMFdfJRCeKxEsVtKwFHwALZfCUk3tIfNR8XiJwc1LmL4dg141JPKtj3
WUdNFJqLGFVPC4OkR4BxajTWsChY64wmCnMxsWPCHcutKBxMVp5mxA1S+aMComToaqTRUQknLTH6
2kHOVEE+VQnjahscNCy0cMBWsSI0TCQcZc5ALkEYckL5A5noWSBhfm2AecMAjbcRWV0pUTh0HE64
TNf0mczcnnQyu/MilaFJCae1nw2fbz1DnVOxyGTlKeZft/Ff8x1BRssfACjTwQAAAABJRU5ErkJg
gg0KLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0xNDkwNDA0NDczOTc4NzE5MTAzMTc1NDcx
MTc0OA0KQ29udGVudC1EaXNwb3NpdGlvbjogZm9ybS1kYXRhOyBuYW1lPSJ0ZXh0Ig0KDQotLWxv
bmcgdGV4dA0KLS13aXRoIGJvdW5kYXJ5DQotLWxvb2thbGlrZXMtLQ0KLS0tLS0tLS0tLS0tLS0t
LS0tLS0tLS0tLS0tLS0xNDkwNDA0NDczOTc4NzE5MTAzMTc1NDcxMTc0OC0tDQo=''')),
'boundary':'---------------------------14904044739787191031754711748',
'files': {'file1': (u'accept.png', 'image/png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0
U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAKfSURBVDjLpZPrS1NhHMf9O3bOdmwDCWRE
IYKEUHsVJBI7mg3FvCxL09290jZj2EyLMnJexkgpLbPUanNOberU5taUMnHZUULMvelCtWF0sW/n
7MVMEiN64AsPD8/n83uucQDi/id/DBT4Dolypw/qsz0pTMbj/WHpiDgsdSUyUmeiPt2+V7SrIM+b
Sss8ySGdR4abQQv6lrui6VxsRonrGCS9VEjSQ9E7CtiqdOZ4UuTqnBHO1X7YXl6Daa4yGq7vWO1D
40wVDtj4kWQbn94myPGkCDPdSesczE2sCZShwl8CzcwZ6NiUs6n2nYX99T1cnKqA2EKui6+TwphA
5k4yqMayopU5mANV3lNQTBdCMVUA9VQh3GuDMHiVcLCS3J4jSLhCGmKCjBEx0xlshjXYhApfMZRP
5CyYD+UkG08+xt+4wLVQZA1tzxthm2tEfD3JxARH7QkbD1ZuozaggdZbxK5kAIsf5qGaKMTY2lAU
/rH5HW3PLsEwUYy+YCcERmIjJpDcpzb6l7th9KtQ69fi09ePUej9l7cx2DJbD7UrG3r3afQHOyCo
+V3QQzE35pvQvnAZukk5zL5qRL59jsKbPzdheXoBZc4saFhBS6AO7V4zqCpiawuptwQG+UAa7Ct3
UT0hh9p9EnXT5Vh6t4C22QaUDh6HwnECOmcO7K+6kW49DKqS2DrEZCtfuI+9GrNHg4fMHVSO5kE7
nAPVkAxKBxcOzsajpS4Yh4ohUPPWKTUh3PaQEptIOr6BiJjcZXCwktaAGfrRIpwblqOV3YKdhfXO
IvBLeREWpnd8ynsaSJoyESFphwTtfjN6X1jRO2+FxWtCWksqBApeiFIR9K6fiTpPiigDoadqCEag
5YUFKl6Yrciw0VOlhOivv/Ff8wtn0KzlebrUYwAAAABJRU5ErkJggg=='''))),
          'file2': (u'add.png', 'image/png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0
U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJvSURBVDjLpZPrS5NhGIf9W7YvBYOkhlko
qCklWChv2WyKik7blnNris72bi6dus0DLZ0TDxW1odtopDs4D8MDZuLU0kXq61CijSIIasOvv94V
TUfLiB74fXngup7nvrnvJABJ/5PfLnTTdcwOj4RsdYmo5glBWP6iOtzwvIKSWstI0Wgx80SBblpK
tE9KQs/We7EaWoT/8wbWP61gMmCH0lMDvokT4j25TiQU/ITFkek9Ow6+7WH2gwsmahCPdwyw75uw
9HEO2gUZSkfyI9zBPCJOoJ2SMmg46N61YO/rNoa39Xi41oFuXysMfh36/Fp0b7bAfWAH6RGi0Hgl
WNCbzYgJaFjRv6zGuy+b9It96N3SQvNKiV9HvSaDfFEIxXItnPs23BzJQd6DDEVM0OKsoVwBG/1V
MzpXVWhbkUM2K4oJBDYuGmbKIJ0qxsAbHfRLzbjcnUbFBIpx/qH3vQv9b3U03IQ/HfFkERTzfFj8
w8jSpR7GBE123uFEYAzaDRIqX/2JAtJbDat/COkd7CNBva2cMvq0MGxp0PRSCPF8BXjWG3FgNHc9
XPT71Ojy3sMFdfJRCeKxEsVtKwFHwALZfCUk3tIfNR8XiJwc1LmL4dg141JPKtj3WUdNFJqLGFVP
C4OkR4BxajTWsChY64wmCnMxsWPCHcutKBxMVp5mxA1S+aMComToaqTRUQknLTH62kHOVEE+VQnj
ahscNCy0cMBWsSI0TCQcZc5ALkEYckL5A5noWSBhfm2AecMAjbcRWV0pUTh0HE64TNf0mczcnnQy
u/MilaFJCae1nw2fbz1DnVOxyGTlKeZft/Ff8x1BRssfACjTwQAAAABJRU5ErkJggg==''')))},
'forms': {'text': u'--long text\r\n--with boundary\r\n--lookalikes--'}}

browser_test_cases['opera8-2png1txt'] = {'data': base64.b64decode(to_bytes('''
LS0tLS0tLS0tLS0tekVPOWpRS21MYzJDcTg4YzIzRHgxOQ0KQ29udGVudC1EaXNwb3NpdGlvbjog
Zm9ybS1kYXRhOyBuYW1lPSJmaWxlMSI7IGZpbGVuYW1lPSJhcnJvd19icmFuY2gucG5nIg0KQ29u
dGVudC1UeXBlOiBpbWFnZS9wbmcNCg0KiVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9h
AAAABGdBTUEAAK/INwWK6QAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAHY
SURBVDjLlVLPS1RxHJynpVu7KEn0Vt+2l6IO5qGCIsIwCPwD6hTUaSk6REoUHeoQ0qVAMrp0COpY
0SUIPVRgSl7ScCUTst6zIoqg0y7lvpnPt8MWKuuu29w+hxnmx8dzzmE5+l7mxk1u/a3Dd/ejDjSs
II/m3vjJ9MF0yt93ZuTkdD0CnnMO/WOnmsxsJp3yd2zfvA3mHOa+zuHTjy/zojrvHX1YqunAZE9M
lpUcZAaZQBNIZUg9XdPBP5wePuEO7eyGQXg29QL3jz3y1oqwbvkhCuYEOQMp/HeJohCbICMUVwr0
DvZcOnK9u7GmQNmBQLJCgORxkneqRmAs0BFmDi0bW9E72PPda/BikwWi0OEHkNR14MrewsTAZF+l
AAWZEH6LUCwUkUlntrS1tiG5IYlEc6LcjYjSYuncngtdhakbM5dXlhgTNEMYLqB9q49MKgsPjTBX
ntVgkDNIgmI1VY2Q7QzgJ9rx++ci3ofziBYiiELQEUAyhB/D29M3Zy+uIkDIhGYvgeKvIkbHxz6T
evzq6ut+ANh9fldetMn80OzZVVdgLFjBQ0tpEz68jcB4ifx3pQeictVXIEETnBPCKMLEwBIZAPJD
767V/ETGwsjzYYiC6vzEP9asLo3SGuQvAAAAAElFTkSuQmCCDQotLS0tLS0tLS0tLS16RU85alFL
bUxjMkNxODhjMjNEeDE5DQpDb250ZW50LURpc3Bvc2l0aW9uOiBmb3JtLWRhdGE7IG5hbWU9ImZp
bGUyIjsgZmlsZW5hbWU9ImF3YXJkX3N0YXJfYnJvbnplXzEucG5nIg0KQ29udGVudC1UeXBlOiBp
bWFnZS9wbmcNCg0KiVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/I
NwWK6QAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJvSURBVDjLhZNNSFRR
FIC/N++9eWMzhkl/ZJqFMQMRFvTvImkXSdKiVRAURBRRW1eZA9EqaNOiFlZEtQxKyrJwUS0K+qEQ
zaTE/AtLHR3HmffuvafFNINDWGdz7z2c7+Nyzr2WiFAIffaMBDW1+B0diAgYgxiDiCDG4DU1QfcL
os+fWAXGYUGIUsXiAliUFER+sBAhVCIIVB7QGtEat1oTbcwVz2LMfwR+gPg+oY0bEa3x6sHdUoVd
niMUj0M2i/j+PwVJa2QUu7YWp34D7mqNWdNApD6Ks24dpvcL4gfJRQXevbutjI4lGRzCS9iYukPo
5dvxVqWQvn6k/2uyoudd60LGEhG43VBGyI4j2ADZ7vDJ8DZ9Img4hw4cvO/3UZ1vH3p7lrWRLwGV
neD4y6G84NaOYSoTVYIFIiAGvXI3OWctJv0TW03jZb5gZSfzl9YBpMcIzUwdzQsuVR9EyR3TeCqm
6w5jZiZQMz8xsxOYzDTi50AMVngJNgrnUweRbwMPiLpHrOJDOl9Vh6HD7GyO52qa0VPj6MwUJpNC
5mYQS/DUJLH3zzRp1cqN8YulTUyODBBzt4X6Ou870z2I8ZHsHJLLYNQ8jusQ6+2exJf9BfivKdAy
mKZiaVdodhBRAagAjIbgzxp20lwb6Vp0jADYkQO6IpHfuoqInSJUVoE2HrpyRQ1tic2LC9p3lSHW
Ph2rJfL1MeVP2weWvHp8s3ziNZ49i1q6HrR1YHGBNnt1dG2Z++gC4TdvrqNkK1eHj7ljQ/ujHx6N
yPw8BFIiKPmNpKar7P7xb/zyT9P+o7OYvzzYSUt8U+TzxytodixEfgN3CFlQMNAcMgAAAABJRU5E
rkJggg0KLS0tLS0tLS0tLS0tekVPOWpRS21MYzJDcTg4YzIzRHgxOQ0KQ29udGVudC1EaXNwb3Np
dGlvbjogZm9ybS1kYXRhOyBuYW1lPSJ0ZXh0Ig0KDQpibGFmYXNlbCDDtsOkw7wNCi0tLS0tLS0t
LS0tLXpFTzlqUUttTGMyQ3E4OGMyM0R4MTktLQ0K''')),
'boundary':'----------zEO9jQKmLc2Cq88c23Dx19',
'files': {'file1': (u'arrow_branch.png', 'image/png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0
U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAHYSURBVDjLlVLPS1RxHJynpVu7KEn0Vt+2
l6IO5qGCIsIwCPwD6hTUaSk6REoUHeoQ0qVAMrp0COpY0SUIPVRgSl7ScCUTst6zIoqg0y7lvpnP
t8MWKuuu29w+hxnmx8dzzmE5+l7mxk1u/a3Dd/ejDjSsII/m3vjJ9MF0yt93ZuTkdD0CnnMO/WOn
msxsJp3yd2zfvA3mHOa+zuHTjy/zojrvHX1YqunAZE9MlpUcZAaZQBNIZUg9XdPBP5wePuEO7eyG
QXg29QL3jz3y1oqwbvkhCuYEOQMp/HeJohCbICMUVwr0DvZcOnK9u7GmQNmBQLJCgORxkneqRmAs
0BFmDi0bW9E72PPda/BikwWi0OEHkNR14MrewsTAZF+lAAWZEH6LUCwUkUlntrS1tiG5IYlEc6Lc
jYjSYuncngtdhakbM5dXlhgTNEMYLqB9q49MKgsPjTBXntVgkDNIgmI1VY2Q7QzgJ9rx++ci3ofz
iBYiiELQEUAyhB/D29M3Zy+uIkDIhGYvgeKvIkbHxz6Tevzq6ut+ANh9fldetMn80OzZVVdgLFjB
Q0tpEz68jcB4ifx3pQeictVXIEETnBPCKMLEwBIZAPJD767V/ETGwsjzYYiC6vzEP9asLo3SGuQv
AAAAAElFTkSuQmCC'''))),
          'file2': (u'award_star_bronze_1.png', 'image/png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0
U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJvSURBVDjLhZNNSFRRFIC/N++9eWMzhkl/
ZJqFMQMRFvTvImkXSdKiVRAURBRRW1eZA9EqaNOiFlZEtQxKyrJwUS0K+qEQzaTE/AtLHR3Hmffu
vafFNINDWGdz7z2c7+Nyzr2WiFAIffaMBDW1+B0diAgYgxiDiCDG4DU1QfcLos+fWAXGYUGIUsXi
AliUFER+sBAhVCIIVB7QGtEat1oTbcwVz2LMfwR+gPg+oY0bEa3x6sHdUoVdniMUj0M2i/j+PwVJ
a2QUu7YWp34D7mqNWdNApD6Ks24dpvcL4gfJRQXevbutjI4lGRzCS9iYukPo5dvxVqWQvn6k/2uy
oudd60LGEhG43VBGyI4j2ADZ7vDJ8DZ9Img4hw4cvO/3UZ1vH3p7lrWRLwGVneD4y6G84NaOYSoT
VYIFIiAGvXI3OWctJv0TW03jZb5gZSfzl9YBpMcIzUwdzQsuVR9EyR3TeCqm6w5jZiZQMz8xsxOY
zDTi50AMVngJNgrnUweRbwMPiLpHrOJDOl9Vh6HD7GyO52qa0VPj6MwUJpNC5mYQS/DUJLH3zzRp
1cqN8YulTUyODBBzt4X6Ou870z2I8ZHsHJLLYNQ8jusQ6+2exJf9BfivKdAymKZiaVdodhBRAagA
jIbgzxp20lwb6Vp0jADYkQO6IpHfuoqInSJUVoE2HrpyRQ1tic2LC9p3lSHWPh2rJfL1MeVP2weW
vHp8s3ziNZ49i1q6HrR1YHGBNnt1dG2Z++gC4TdvrqNkK1eHj7ljQ/ujHx6NyPw8BFIiKPmNpKar
7P7xb/zyT9P+o7OYvzzYSUt8U+TzxytodixEfgN3CFlQMNAcMgAAAABJRU5ErkJggg==''')))},
'forms': {'text': u'blafasel öäü'}}

browser_test_cases['webkit3-2png1txt'] = {'data': base64.b64decode(to_bytes('''
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
melp14H1cYUZ3J31fZyTE1zA7fVw+n0cERSg8v2RUS5pPqeArNtlZmGBwqtjY+skwYig80lXBCff
5OvANFeSxzIRojge5+j8Uu9dXOD5Pt6o41jAz1W69uznMQ8wgOf79LpdNNTHwBT22r1ebDwPt0h8
DbQAFTADGGvp9PtxCntjYAa7zW43wVpca3HyZZsJaAF0C/k+4vs0wzDJYHcMfCSyHyfJzq/n50NT
raKVwhl1H3cCpAsphVut8tvz58M4SXaKn8X4pFzB1lG/P2gOBuhaDYxBJhqR5e8Yg56f53gwoNHr
Da9gq+CMz7JSauoz+HgFvr1trX+vXPZKUYSbJCMTA+K6xMYw8Dx+7Pfjw+Fw+Dt8/h38ALwQkeg6
cAaoLcLyp/BlVam1dz3PWdDaqbkjdwVpymmaZn9FUXouUn8M3zyDJvAC+PclYA6dBmpA5SO4dxM+
mIf3fVgCGMLfz+CPf+CXPfgZCIFz4ExEkpeWfH0opZzcKYUsI38nIy5D4BK4kgnAfwLblOaQdQsS
AAAAAElFTkSuQmCCDQotLS0tLS1XZWJLaXRGb3JtQm91bmRhcnlqZFNGaGNBUms4ZnlHTnk2DQpD
b250ZW50LURpc3Bvc2l0aW9uOiBmb3JtLWRhdGE7IG5hbWU9InRleHQiDQoNCnRoaXMgaXMgYW5v
dGhlciB0ZXh0IHdpdGggw7xtbMOkw7x0cw0KLS0tLS0tV2ViS2l0Rm9ybUJvdW5kYXJ5amRTRmhj
QVJrOGZ5R055Ni0tDQo=''')),
'boundary':'----WebKitFormBoundaryjdSFhcARk8fyGNy6',
'files': {'file1': (u'gtk-apply.png', 'image/png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAABHNCSVQICAgIfAhkiAAAAAlwSFlz
AAAN1wAADdcBQiibeAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAANnSURB
VDiNldJ9aJVVHAfw7znPuS/PvW4405WbLWfbsBuNbramq5Tp7mLqIFPXINlwpAitaCAPjWKgBdXz
R2TBpEZoadAyCVGndttCFNxqLXORK7x3y704NlzXzfs8d89znuf0R/fKk03xHvjCOZxzPpzzO4cI
IZBuC6nsGYmRrwFMWVw0hxV+PDVH0gVDKvNSRgZfrm5+QCISOi58pY1MXhm1uHg+rPDfabqnoxJp
KQ2snf/gwgKY3ut4pfodX/lTGwokRt4AgLTAkMoK3cz7enVJg/fyTCdGE/3gwsTo+LBu2+J82qDE
6IEXyrd7YvYwbpgjyPOtQHTikvhz+NKgsNGWFhhSWU3uwqWPBx9aRwfjPTCFgXx5JY50tumWKbaF
FS7uGQypLINKZH/tukb/kN6DSSOCFfO3oqu/3biZiH0ZVvjF1Np7AiVG31sdXO/P8GfhqtaLbE8B
qOlBZ++xuMXFbudaljxBDnNJHbZlFwF407bFh6krhFRW7Jcztlc9Uee5HD+DaWsCTy/YgbaOvZpl
2Y1hhU87QVLxvpQpMfpzfeXuZfmLA/Rw1wdaZOS3Pm7aNQDGJUZ/qatqKs5etIj03TiKQv8aaFOW
OHRm30+nm4zS229DmVs6Ulm6OW/50iD9G1Hsqnrbt2lNwyoXYwMAPnk4N1D4aO4qEtW6wagHeZ4S
fNP1mW6Zdt1c5WEE8Lll5qKCQbdiGIh/h+JlK6WixcHM4z2fb9tUtkOO6hdw3Yzi2axdON33xaxu
zLSGFf7HXCA1Dav+5Nn2Kyd7DyYK5bXw0QWIJM4j7rqGmvKd8gwZw5D+I3K8jyGhmzj366lpi4uW
Oz0gEUIgpDKPxGjr/VlLanZubJknXLMYiH8PjccwK26C27Oouu8tfHysWbs6HnkxrPATdwVTLaSy
zW63+8BLzzX6H1lSSrtjBzFpRPBkZi0mrk3Z7Z2tP5xqMiruhP0PTKL5EqMnSgKr87eUvSqPGf3I
psux53CDpie0QFjhf90NhBDiVlJ1LaqmcqXq2l/7aU7826E94rWjQb3iXbYXgAzAC8ADwI1//zF1
OkQIAUIIBSAlc6tfpkjr52XTj4SFi937eP3MmDAB2I5YyaT63AmyuVDHmAAQt0FOzARg/aeGhBCS
3EjnCBygMwKAnXL+AdDkiZ/xYgR3AAAAAElFTkSuQmCC'''))),
          'file2': (u'gtk-no.png', 'image/png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAABHNCSVQICAgIfAhkiAAAAAlwSFlz
AAAN1wAADdcBQiibeAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAM1SURB
VDiNrZTPaxtHFMc/M7uzs7KobckyDjQxtoPbnlJyMBRKgsGFHkwvvfbuU/+BQCilBHrof+BT7zmV
4lsNxqUUXBo1tIdSsCy3uI7jrKSVJUveX68H7QpHSW4d+O6PeW8/vJn3nVUiwv853DcFHip1X8OG
A+sp3AVwoJ7CXga7j0T2X/edmqzwgVIVC9teqbS5tLxsZqtV9625OQAugoBOu500G404Ggx2rmDr
a5H2G4FfKPUh8P3KysrUe3fuWA14c3NoYxARsjgmbrXIlOLPp0+vGo3GJfDJVyI/vQJ8oFTFwOHa
2lqlVqmgSyXM9PQoSwQRgVxxGCJpStBuc3Bw0I7hdlGpLsgWtpdu3ZqqlssMTk6QJCFqtYiC4BVl
cczl0RGVcpmlxcUpC9sFRxcNMNZurq6u2rBex7GWtNUiDQIkCMiKe6tF2mqRBAHKdQmfPOGd1VVr
rN18qNT9cZc1bLy9sGCS01MIQ3QYohwHnS9RFfssQiaCZBk6SZAwJDo95eaNG+bw+HgD2HdzO6zP
lkqu6nSwgDo7Q/s+OstQ14CZCGTZiB1Fo9xOh5npadeB9XGFGdyd9X2ckxNcwO31cPp9HBEUoPL9
kVEuaT6ngKzbZWZhgcKrY2PrJMGIoPNJVwQn3+TrwDRXkscyEaI4Hufo/FLvXVzg+T7eqONYwM9V
uvbs5zEPMIDn+/S6XTTUx8AU9tq9Xmw8D7dIfA20ABUwAxhr6fT7cQp7Y2AGu81uN8FaXGtx8mWb
CWgBdAv5PuL7NMMwyWB3DHwksh8nyc6v5+dDU62ilcIZdR93AqQLKYVbrfLb8+fDOEl2ip/F+KRc
wdZRvz9oDgboWg2MQSYakeXvGIOen+d4MKDR6w2vYKvgjM+yUmrqM/h4Bb69ba1/r1z2SlGEmyQj
EwPiusTGMPA8fuz348PhcPg7fP4d/AC8EJHoOnAGqC3C8qfwZVWptXc9z1nQ2qm5I3cFacppmmZ/
RVF6LlJ/DN88gybwAvj3JWAOnQZqQOUjuHcTPpiH931YAhjC38/gj3/glz34GQiBc+BMRJKXlnx9
KKWc3CmFLCN/JyMuQ+ASuJIJwH8C25TmkHULEgAAAABJRU5ErkJggg==''')))},
'forms': {'text': u'this is another text with ümläüts'}}

browser_test_cases['ie6-2png1txt'] = {'data': base64.b64decode(to_bytes('''
LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS03ZDkxYjAzYTIwMTI4DQpDb250ZW50LURpc3Bv
c2l0aW9uOiBmb3JtLWRhdGE7IG5hbWU9ImZpbGUxIjsgZmlsZW5hbWU9IkM6XFB5dGhvbjI1XHd6
dGVzdFx3ZXJremV1Zy1tYWluXHRlc3RzXG11bHRpcGFydFxmaXJlZm94My0ycG5nMXR4dFxmaWxl
MS5wbmciDQpDb250ZW50LVR5cGU6IGltYWdlL3gtcG5nDQoNColQTkcNChoKAAAADUlIRFIAAAAQ
AAAAEAgGAAAAH/P/YQAAAARnQU1BAACvyDcFiukAAAAZdEVYdFNvZnR3YXJlAEFkb2JlIEltYWdl
UmVhZHlxyWU8AAABnUlEQVQ4y6VTMWvCQBS+qwEFB10KGaS1P6FDpw7SrVvzAwRRx04VCk4K6iAo
DhLXdhFcW9qhZCk4FQoW0gp2U4lQRDAUS4hJmn5Xgg2lsQ198PHu3b3vu5d3L9S2bfIf47wOer1e
wzTNtGEYBP48kUjkfsrb8BIAMb1cLovwRfi07wrYzcCr4/1/Am4FzzhzBGZeefR7E7vd7j0Iu4wY
jUYDBMfD0dBiMUQfstns3toKkHgF6EgmqqruW6bFiHcsxr70awVu63Q6NiOmUinquwfMdF1f28CV
gCRJx0jMAQ1BEFquRn7CbYVCYZVbr9dbnJMohoIh9kViu90WEW9nMpmxu4JyubyF/VEsFiNcgCPy
oyxiu7XhCPBzdU4s652VnUccbDabPLyN2C6VSmwdhFgel5DB84AJb64mEUlvmqadTKcv40gkUkUs
g1DjeZ7iRsrWgByP71T7/afxYrHIYry/eoBD9mxsaK4VRamFw2EBQknMAWGvRClNTpQJAfkCxFNg
Bmiez1ipVA4hdgQcOD/TLfylKIo3vubgL/YBnIw+ioOMLtwAAAAASUVORK5CYIINCi0tLS0tLS0t
LS0tLS0tLS0tLS0tLS0tLS0tLS0tN2Q5MWIwM2EyMDEyOA0KQ29udGVudC1EaXNwb3NpdGlvbjog
Zm9ybS1kYXRhOyBuYW1lPSJmaWxlMiI7IGZpbGVuYW1lPSJDOlxQeXRob24yNVx3enRlc3Rcd2Vy
a3pldWctbWFpblx0ZXN0c1xtdWx0aXBhcnRcZmlyZWZveDMtMnBuZzF0eHRcZmlsZTIucG5nIg0K
Q29udGVudC1UeXBlOiBpbWFnZS94LXBuZw0KDQqJUE5HDQoaCgAAAA1JSERSAAAAEAAAABAIBgAA
AB/z/2EAAAAEZ0FNQQAAr8g3BYrpAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccll
PAAAAlFJREFUGBmlwd1rzXEcwPH353d+51jO5jDZFpnnJNaiUSK5mkJKMYkUSS1RSvwDpnFBkYeY
O2p2sZRceCh5mpKnUXZssVaO2Q4Hw9nO+Z3v52O/ldoFF8vrJWbG/5CNB67uXbm65lgma3EzQBVT
xanD1FBTzDnUDHMOp8qEWPCroyN1uPVE3Rm/ZkXNqWhR3CsvYiziv7LuFHDGzwbmZTM/GavBwDyG
+eaMhm1zGavdjT2EfDMllC84DDA1nIJiqBpOFVcwXMEIPt8l+/wykeIq9pXd49XZ/Tt8zAiJJ4gZ
5gkmhqjgeYKIh4hDM9eJ9j6lomo7iVmL+dY9n+StpuO+U0fIA0wEBCIGKqBqRAwK6dvEcm+Iz1tB
5l0HMclTMqGC4smVCd/UGCECZniAiYCACOT77yM/npCYvYZcbzOx8ULPyyQDWZBcptpTdfwhIiBC
yANy6fsUvtwmMWctQx8vItGvRItLiFuGK6nlLN3X2ukVgoARIogIIRGhL3md7IebJOZuYCh1Di8a
kB+YSfphO1NqG/g4OJGQZ04JRQABRIT+5A1+pNooW7iO/KcmIjEjNzCD9KMXVGw6T1H5AkyVkK+q
/CFAV1szhe+vKchUel+fZlJZjKHMdL49S1K55QLRxDRCakbIT3X3tNSfDOrUOdQptdLE5vpLvG0+
SOeDNsZVVvO9L8WNoa30NTzGVFEl1MIwMTNGO7JnUXBoV72P53h55xo93V0/E1NKV9YebW/nL8TM
GK1uVengktnl/rIFs7Borm2wP71zfeOr9/zDb6ZFKM6WU+GQAAAAAElFTkSuQmCCDQotLS0tLS0t
LS0tLS0tLS0tLS0tLS0tLS0tLS0tLTdkOTFiMDNhMjAxMjgNCkNvbnRlbnQtRGlzcG9zaXRpb246
IGZvcm0tZGF0YTsgbmFtZT0idGV4dCINCg0KaWU2IHN1Y2tzIDotLw0KLS0tLS0tLS0tLS0tLS0t
LS0tLS0tLS0tLS0tLS03ZDkxYjAzYTIwMTI4LS0NCg==''')),
'boundary':'---------------------------7d91b03a20128',
'files': {'file1': (u'file1.png', 'image/x-png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0
U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAGdSURBVDjLpVMxa8JAFL6rAQUHXQoZpLU/
oUOnDtKtW/MDBFHHThUKTgrqICgOEtd2EVxb2qFkKTgVChbSCnZTiVBEMBRLiEmafleCDaWxDX3w
8e7dve+7l3cv1LZt8h/jvA56vV7DNM20YRgE/jyRSOR+ytvwEgAxvVwui/BF+LTvCtjNwKvj/X8C
bgXPOHMEZl559HsTu93uPQi7jBiNRgMEx8PR0GIxRB+y2eze2gqQeAXoSCaqqu5bpsWIdyzGvvRr
BW7rdDo2I6ZSKeq7B8x0XV/bwJWAJEnHSMwBDUEQWq5GfsJthUJhlVuv11uckyiGgiH2RWK73RYR
b2cymbG7gnK5vIX9USwWI1yAI/KjLGK7teEI8HN1TizrnZWdRxxsNps8vI3YLpVKbB2EWB6XkMHz
gAlvriYRSW+app1Mpy/jSCRSRSyDUON5nuJGytaAHI/vVPv9p/FischivL96gEP2bGxorhVFqYXD
YQFCScwBYa9EKU1OlAkB+QLEU2AGaJ7PWKlUDiF2BBw4P9Mt/KUoije+5uAv9gGcjD6Kg4wu3AAA
AABJRU5ErkJggg=='''))),
          'file2': (u'file2.png', 'image/x-png', base64.b64decode(to_bytes('''
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0RVh0
U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAJRSURBVBgZpcHda81xHMDx9+d3fudYzuYw
2RaZ5yTWolEiuZpCSjGJFEktUUr8A6ZxQZGHmDtqdrGUXHgoeZqSp1F2bLFWjtkOB8PZzvmd7+dj
v5XaBRfL6yVmxv+QjQeu7l25uuZYJmtxM0AVU8Wpw9RQU8w51AxzDqfKhFjwq6Mjdbj1RN0Zv2ZF
zaloUdwrL2Is4r+y7hRwxs8G5mUzPxmrwcA8hvnmjIZtcxmr3Y09hHwzJZQvOAwwNZyCYqgaThVX
MFzBCD7fJfv8MpHiKvaV3ePV2f07fMwIiSeIGeYJJoao4HmCiIeIQzPXifY+paJqO4lZi/nWPZ/k
rabjvlNHyANMBAQiBiqgakQMCunbxHJviM9bQeZdBzHJUzKhguLJlQnf1BghAmZ4gImAgAjk++8j
P56QmL2GXG8zsfFCz8skA1mQXKbaU3X8ISIgQsgDcun7FL7cJjFnLUMfLyLRr0SLS4hbhiup5Szd
19rpFYKAESKICCERoS95neyHmyTmbmAodQ4vGpAfmEn6YTtTahv4ODiRkGdOCUUAAUSE/uQNfqTa
KFu4jvynJiIxIzcwg/SjF1RsOk9R+QJMlZCvqvwhQFdbM4XvrynIVHpfn2ZSWYyhzHS+PUtSueUC
0cQ0QmpGyE9197TUnwzq1DnUKbXSxOb6S7xtPkjngzbGVVbzvS/FjaGt9DU8xlRRJdTCMDEzRjuy
Z1FwaFe9j+d4eecaPd1dPxNTSlfWHm1v5y/EzBitblXp4JLZ5f6yBbOwaK5tsD+9c33jq/f8w2+m
RSjOllPhkAAAAABJRU5ErkJggg==''')))},
'forms': {'text': u'ie6 sucks :-/'}}

class TestWerkzeugExamples(unittest.TestCase):
    def test_werkzeug_examples(self):
        """Tests multipart parsing against data collected from webbrowsers"""
        for name in browser_test_cases:
            boundary = browser_test_cases[name]['boundary']
            files = browser_test_cases[name]['files']
            forms = browser_test_cases[name]['forms']
            env = {'REQUEST_METHOD': 'POST',
                   'CONTENT_TYPE': 'multipart/form-data; boundary=%s'%boundary,
                   'wsgi.input': BytesIO(browser_test_cases[name]['data'])}
            rforms, rfiles = mp.parse_form_data(env, strict=True, charset='utf8')
            for field in files:
                self.assertEqual(rfiles[field].name, field)
                self.assertEqual(rfiles[field].filename, files[field][0])
                self.assertEqual(rfiles[field].content_type, files[field][1])
                self.assertEqual(rfiles[field].file.read(), to_bytes(files[field][2]))
            for field in forms:
                self.assertEqual(rforms[field], forms[field])
