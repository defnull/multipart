# -*- coding: utf-8 -*-
from tempfile import TemporaryFile
from wsgiref.headers import Headers
import re, sys, io
import urlparse
sys.path.insert(0,'/home/marc/coding/bottle/')
from bottle import MultiDict
'''
TODO

[ ] works in Python 2.5+ and 3.x (2to3).
[ ] consumes bytes regardless of python version.
[x] has no dependencies.
[x] passes all the tests in werkzeug/test/test_formparser.py.
[x] produces useful error messages.
[x] supports uploads of unknown size (missing content-length header).
[x] uses fast memory mapped file-likes (io.BytesIO) for small uploads.
[x] uses tempfiles for big uploads.
[x] has an upper memory limit to prevent DOS attacks.
[x] has an upper disk size limit to prevent DOS attacks.
[x] supports multipart and url-encoded data.
[ ] supports base46 and quoted-printable encoding
[x] uses stream.read() only (no stream.readline(size)) and therefor works directly on wsgi.input.
[x] works directly on an environ dict and does not require the features of the request object.
'''
##############################################################################
################################ Header Parser ################################
##############################################################################

def header_unquote(val, filename=False):
    if val[0] == val[-1] == '"':
        val = val[1:-1]
        if val[1:3] == ':\\' or val[:2] == '\\\\': 
            val = val.split('\\')[-1] # fix ie6 bug: full path --> filename
        return val.replace('\\\\','\\').replace('\\"','"')
    return val

_str = '[^\\(\\)\\<\\>\\@\\,\\;\\:\\\\\\"\\/\\[\\]\\?\\=\\{\\}\\ \\\t]+'
_qstr = '"(?:\\\\.|[^"])*"' # Quoted string
_value = '(?:%s|%s)' % (_str, _qstr) # Save or quoted string
_option = '(?:;|^)\s*(%s)\s*=\s*(%s)' % (_str, _value) # key=value part of an options header
_re_option = re.compile(_option)

def parse_options_header(header, options=None):
    if ';' not in header:
        return header.lower().strip(), {}
    ctype, tail = header.split(';', 1)
    options = options or {}
    for match in _re_option.finditer(tail):
        key = header_unquote(match.group(1)).lower().strip()
        value = header_unquote(match.group(2), key=='filename')
        options[key] = value
    return ctype, options

assert parse_options_header('form-data; name="Test"; filename="Test.txt"')[0] == 'form-data'
assert parse_options_header('form-data; name="Test"; filename="Test.txt"')[1]['name'] == 'Test'
assert parse_options_header('form-data; name="Test"; filename="Test.txt"')[1]['filename'] == 'Test.txt'
assert parse_options_header('form-data; name="Test"; FileName="Test.txt"')[1]['filename'] == 'Test.txt'
assert parse_options_header('form-data; filename="C:\\test\\bla.txt"')[1]['filename'] == 'bla.txt'
assert parse_options_header('form-data; filename="\\\\test\\bla.txt"')[1]['filename'] == 'bla.txt'
assert parse_options_header('form-data; name="cb_file_upload_multiple"; filename="\\\\192.168.1.5\\Users\\Dave\\2010 Meeting Minutes\\Sellersburg Town Council Meeting 02-22-2010doc.doc"')[1]['filename'] == 'Sellersburg Town Council Meeting 02-22-2010doc.doc'

##############################################################################
################################## Multipart ##################################
##############################################################################

MAXBUF = 10*1024 # 10kb
MAXMEMFILE = 500*1024  # 500kb
MAXMEM = 1024**2 # 1mb
MAXDISK = 1024**3 # 1gb

def tob(data, enc='utf8'): # Convert strings to bytes (py2 and py3)
    return data.encode(enc) if isinstance(data, unicode) else data

def parse_line(line):
    if line[-2:] == '\r\n': return line[:-2], '\r\n'
    elif line[-1:] == '\n': return line[:-1], '\n'
    elif line[-1:] == '\r': return line[:-1], '\r'
    else:                   return line, ''

assert parse_line('foo') == ('foo','')
assert parse_line('foo\n') == ('foo','\n')
assert parse_line('foo\r\n') == ('foo','\r\n')
assert parse_line('foo\r') == ('foo','\r')
assert parse_line('\n') == ('','\n')
assert parse_line('\r\n') == ('','\r\n')
assert parse_line('') == ('','')
assert parse_line('\n\r') == ('\n','\r')

def iterlines(fp, maxread=-1):
    ''' Iterate over a binary file-like object line by line. Line endings are
        preserved if the line fits into maxbuf. If not, the line is returned in
        chuncks.
    
        :parm fp: A file-like object with a ``fp.read(size)`` method.
        :parm maxread: The maximum number of bytes to read from the file.   
    '''
    read = fp.read
    while 1:
        lines = read(MAXBUF if maxread < 0 else min(MAXBUF, maxread))
        maxread -= len(lines)
        if not lines: break
        for line in lines.splitlines(True):
            yield line

t = iterlines(io.BytesIO('abc\ndef\r\nghi\rfoo'))
assert t.next() == 'abc\n'
assert t.next() == 'def\r\n'
assert t.next() == 'ghi\r'
assert t.next() == 'foo'
t = iterlines(io.BytesIO('abcde'), 3)
assert t.next() == 'abc'
t = iterlines(io.BytesIO(('abc'*MAXBUF)+'x\n'))
assert len(t.next()) == MAXBUF
assert len(t.next()) == MAXBUF
assert len(t.next()) == MAXBUF
assert t.next() == 'x\n'
del t

def copy_file(stream, target, maxread=-1):
    ''' Read from :stream and write to :target until :maxread or EOF. '''
    size = 0
    while 1:
        part = stream.read(MAXBUF if maxread < 0 else min(MAXBUF, maxread-size))
        if not part: return size
        target.write(part)
        size += len(part)
    return size

t = io.BytesIO()
assert copy_file(io.BytesIO('abc'), t) == 3
t.seek(0)
assert t.read() == 'abc'
del t

class MultipartError(ValueError): pass

class MultipartPart(object):
    def __init__(self):
        self.headerlist = []
        self.headers = Headers(self.headerlist)
        self.file = False
        self.size = 0
        self._buf = ''
        self.disposition, self.name, self.filename = None, None, None
        self.content_type, self.charset = None, None

    def write(self, line):
        self.write_body(line) if self.file else self.write_header(line)

    def write_header(self, line):
        line, nl = parse_line(line)
        line = line.decode(self.charset or 'latin9')
        if not nl: raise MultipartError('Unexpected end of line in header.')
        if not line.strip(): # blank line -> end of header segment
            self.finish_header()
        elif line[0] in ' \t' and self.headerlist:
            name, value = self.headerlist.pop()
            self.headerlist.append(name, value+line.strip())
        else:
            if ':' not in line:
                raise MultipartError("Syntax error in header: No colon.")
            name, value = line.split(':', 1)
            self.headerlist.append((name.strip(), value.strip()))

    def write_body(self, line):
        if not line: return # This does not even flush the buffer
        line, nl = parse_line(line)
        self.size += len(line) + len(self._buf)
        self.file.write(self._buf + line)
        self._buf = nl
        if self.content_length > 0 and self.size > self.content_length:
            raise MultipartError('Size of body exceeds Content-Length header.')
        if self.size > MAXMEMFILE and isinstance(self.file, io.BytesIO):
            self.file, old = TemporaryFile(mode='w+b'), self.file
            old.seek(0)
            file_copy(old, self.file, self.size)

    def finish_header(self):
        self.file = io.BytesIO()
        cdis = self.headers.get('Content-Disposition','')
        ctype = self.headers.get('Content-Type','')
        clen = self.headers.get('Content-Length','-1')
        if not cdis:
            raise MultipartError('Content-Disposition header is missing.')
        self.disposition, self.options = parse_options_header(cdis)
        self.name = self.options.get('name')
        self.filename = self.options.get('filename')
        self.content_type, options = parse_options_header(ctype)
        self.charset = options.get('charset')
        self.content_length = int(self.headers.get('Content-Length','-1'))

    def is_buffered(self):
        ''' Return true if the data is fully buffered in memory.'''
        return isinstance(self.file, io.BytesIO)

    @property
    def value(self):
        if not self.file: return None
        self.file.seek(0)
        return self.file.read()
    
    def save_as(self, path):
        self.file.seek(0)
        with open(path, 'wb') as fp:
            size = copy_file(self.file, fp)
        return size

def parse_multipart(stream, boundary, content_length=-1):
    ''' Yield :class:`MultipartPart` instances from an multipart byte stream.
    
        :param stream: A file-like stream. Must implement ``.read(size)``.
        :param boundary: The multipart boundary as a byte string.
        :param content_length: The maximum number of bytes to read. 
    '''
    lines, line = iterlines(stream, content_length), ''
    separator, terminator = '--'+boundary, '--'+boundary+'--'
    # Consume first boundary. Ignore leading blank lines
    for line in lines:
        if line.strip(): break
    if not line or parse_line(line)[0] != separator:
        raise MultipartError("Stream does not start with boundary")
    # For each part in stream...
    part = MultipartPart()
    mem_limit, disk_limit = MAXMEM, MAXDISK
    for line in lines:
        line, nl = parse_line(line)
        if line == terminator:
            yield part
            break
        elif line == separator:
            yield part
            if part.is_buffered(): mem_limit  -= part.size
            else:                  disk_limit -= part.size
            part = MultipartPart()
        else:
            part.write(line+nl)
            if part.is_buffered() and mem_limit <= part.size:
                raise MultipartError("Memory limit reached. Increase MAXMEM.")
            elif not part.is_buffered() and disk_limit <= part.size:
                raise MultipartError("Disk limit reached. Increase MAXDISK.")
    if line != terminator:
        raise MultipartError("Unexpected end of multipart stream.")

##############################################################################
#################################### WSGI ####################################
##############################################################################

def parse_form_data(environ, charset='utf8', strict=False):
    ''' Parse form data from an environ dict and returns two :class:`MultiDict`
        instances. The first contains form fields with unicode keys and values.
        The second contains file uploads with unicode keys and
        :class:`MultipartPart` instances as values. Catch
        :exc:`ValueError` and :exc:`IndexError` to be sure.
        
        :param environ: An WSGI environment dict.
        :param charset: The charset to use if unsure. (default: utf8)
        :param strict: If true, raise :exc:`MultipartError` on parsing errors.
    '''
        
    forms, files = MultiDict(), MultiDict()
    try:
        if environ.get('REQUEST_METHOD','GET').upper() not in ('POST', 'PUT'):
            raise MultipartError("Request method other than POST or PUT.")
        content_length = min(int(environ.get('CONTENT_LENGTH', '-1')), MAXDISK)
        content_type = environ.get('CONTENT_TYPE', '')
        if not content_type:
            raise MultipartError("Missing Content-Type header.")
        content_type, options = parse_options_header(content_type)
        stream = environ.get('wsgi.input') or io.BytesIO()
        charset = options.get('charset', charset) # Honor a verbose browser
        if content_type == 'multipart/form-data':
            boundary = options.get('boundary','')
            if not boundary:
                raise MultipartError("No boundary for multipart/form-data.")
            for part in parse_multipart(stream, boundary, content_length):
                codec = part.charset or charset
                name = part.name.decode(codec) if part.name else None
                if part.filename:
                    files[name] = part
                elif part.is_buffered():
                    forms[name] = part.value.decode(codec)
        elif content_type in ('application/x-www-form-urlencoded',
                              'application/x-url-encoded'):
            if content_length > MAXMEM:
                raise MultipartError("Request to big. Increase MAXMEM.")
            data = stream.read(MAXMEM).decode(charset)
            for key, value in urlparse.parse_qs(data, keep_blank_values=True):
                forms[key] = value
        elif strict:
            raise MultipartError("Unsupported content type.")
    except MultipartError:
        if strict: raise
    return forms, files

"""
    werkzeug.formparser test
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Tests the form parsing capabilties.  Some of them are also tested from
    the wrappers.

    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""

##############################################################################
#################################### Tests ####################################
##############################################################################

def test_multipart():
    """Tests multipart parsing against data collected from webbrowsers"""
    from os.path import join, dirname
    resources = join(dirname(__file__), 'multipart')

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
        folder = join(resources, name)
        data = open(join(folder, 'request.txt'), 'rb')
        data.seek(0)
        result = list(parse_multipart(data, boundary))
        for part in result:
            if part.filename:
                tfilename, tname, tctype, tfile = files.pop(0)
                print repr(tfilename), repr(part.filename)
                assert tfilename == part.filename
                assert tname == part.name
                assert tctype == part.content_type
                part.file.seek(0)
                assert open(join(folder, tfile),'rb').read() == part.file.read()
                assert open(join(folder, tfile),'rb').read() == part.value
            else:
                assert part.value.decode(part.charset or 'utf8') == text
    return True

assert test_multipart()

def test_end_of_file_multipart():
    """Test for multipart files ending unexpectedly"""
    # This test looks innocent but it was actually timeing out in
    # the Werkzeug 0.5 release version (#394)
    data = (
        '--foo\r\n'
        'Content-Disposition: form-data; name="test"; filename="test.txt"\r\n'
        'Content-Type: text/plain\r\n\r\n'
        'file contents and no end'
    )
    try:
        return list(parse_multipart(io.BytesIO(data), 'foo'))
    except Exception, e:
        return e

assert isinstance(test_end_of_file_multipart(), MultipartError)
assert test_end_of_file_multipart().args[0] == 'Unexpected end of multipart stream.'

def test_parse_form_data_put_without_content():
    """A PUT without a Content-Type header returns empty data

    Both rfc1945 and rfc2616 (1.0 and 1.1) say "Any HTTP/[1.0/1.1] message
    containing an entity-body SHOULD include a Content-Type header field
    defining the media type of that body."  In the case where either
    headers are omitted, parse_form_data should still work.
    """
    env = {}
    env['REQUEST_METHOD']='POST'
    form, files = parse_form_data(env)
    assert len(form) == 0
    assert len(files) == 0
    return True

assert test_parse_form_data_put_without_content()

def test_parse_form_data_get_without_content():
    """GET requests without data, content type and length returns no data"""
    env = {}
    env['REQUEST_METHOD'] = 'GET'
    form, files = parse_form_data(env)
    assert len(form) == 0
    assert len(files) == 0
    return True

assert test_parse_form_data_get_without_content()

def test_broken_multipart():
    """Broken multipart does not break the applicaiton"""
    data = (
        '--foo\r\n'
        'Content-Disposition: form-data; name="test"; filename="test.txt"\r\n'
        'Content-Transfer-Encoding: base64\r\n'
        'Content-Type: text/plain\r\n\r\n'
        'broken base 64'
        '--foo--'
    )
    data = io.BytesIO(data)
    data.seek(0)
    env = {}
    env['REQUEST_METHOD'] = 'POST'
    env['CONTENT_TYPE'] = 'multipart/form-data; boundary=foo'
    env['wsgi.input'] = data
    try:
        form, files = parse_form_data(env, strict=True)
    except MultipartError, e:
        return e

#TODO: actually test base64 errors...
assert isinstance(test_broken_multipart(), MultipartError)
assert test_broken_multipart().args[0] == 'Unexpected end of multipart stream.'


def test_multipart_file_no_content_type():
    """Chrome does not always provide a content type."""
    data = (
        '--foo\r\n'
        'Content-Disposition: form-data; name="test"; filename="test.txt"\r\n\r\n'
        'file contents\r\n--foo--'
    )
    data = io.BytesIO(data)
    data.seek(0)
    env = {}
    env['REQUEST_METHOD'] = 'POST'
    env['CONTENT_TYPE'] = 'multipart/form-data; boundary=foo'
    env['wsgi.input'] = data
    forms, files = parse_form_data(env, strict=True)
    assert files['test'].filename == 'test.txt'
    assert files['test'].value == 'file contents'
    return True

assert test_multipart_file_no_content_type()


def test_extra_newline_multipart():
    """Test for multipart uploads with extra newlines"""
    # this test looks innocent but it was actually timeing out in
    # the Werkzeug 0.5 release version (#394)
    data = (
        '\r\n\r\n--foo\r\n'
        'Content-Disposition: form-data; name="foo"\r\n\r\n'
        'a string\r\n'
        '--foo--'
    )
    data = io.BytesIO(data)
    data.seek(0)
    env = {}
    env['REQUEST_METHOD'] = 'POST'
    env['CONTENT_TYPE'] = 'multipart/form-data; boundary=foo'
    env['wsgi.input'] = data
    forms, files = parse_form_data(env, strict=True)
    assert not files
    assert forms['foo'] == 'a string'
    return True

assert test_extra_newline_multipart()


def test_multipart_headers():
    """Test access to multipart headers"""
    data = ('--foo\r\n'
            'Content-Disposition: form-data; name="foo"; filename="foo.txt"\r\n'
            'X-Custom-Header: bla\r\n'
            'Content-Type: text/plain; charset=utf-8\r\n\r\n'
            'file contents, just the contents\r\n'
            '--foo--')
    data = io.BytesIO(data)
    data.seek(0)
    env = {}
    env['REQUEST_METHOD'] = 'POST'
    env['CONTENT_TYPE'] = 'multipart/form-data; boundary=foo'
    env['wsgi.input'] = data
    forms, files = parse_form_data(env, strict=True)
    assert files['foo'].content_type == 'text/plain'
    assert files['foo'].headers['content-type'] == 'text/plain; charset=utf-8'
    assert files['foo'].headers['x-custom-header'] == 'bla'
    return True

assert test_multipart_headers()


def test_nonstandard_line_endings():
    """Test nonstandard line endings of multipart form data"""
    for nl in '\n', '\r', '\r\n':
        data = nl.join((
            '--foo',
            'Content-Disposition: form-data; name=foo',
            '',
            'this is just bar',
            '--foo',
            'Content-Disposition: form-data; name=bar',
            '',
            'blafasel',
            '--foo--'
        ))
        data = io.BytesIO(data)
        data.seek(0)
        env = {}
        env['REQUEST_METHOD'] = 'POST'
        env['CONTENT_TYPE'] = 'multipart/form-data; boundary=foo'
        env['wsgi.input'] = data
        forms, files = parse_form_data(env, strict=True)
        assert forms['foo'] == 'this is just bar'
        assert forms['bar'] == 'blafasel'
        return True

assert test_nonstandard_line_endings()

