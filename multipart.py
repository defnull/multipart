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

_special = re.escape('()<>@,;:\\"/[]?={} \t\n\r')
_re_special = re.compile('[%s]' % _special)
_qstr = '"(?:\\\\.|[^"])*"' # Quoted string
_value = '(?:[^%s]+|%s)' % (_special, _qstr) # Save or quoted string
_option = '(?:;|^)\s*([^%s]+)\s*=\s*(%s)' % (_special, _value)
_re_option = re.compile(_option) # key=value part of an Content-Type like header

def header_quote(val):
    if not _re_special.match(val):
        return val
    return '"' + val.replace('\\','\\\\').replace('"','\\"') + '"'

def header_unquote(val, filename=False):
    if val[0] == val[-1] == '"':
        val = val[1:-1]
        if val[1:3] == ':\\' or val[:2] == '\\\\': 
            val = val.split('\\')[-1] # fix ie6 bug: full path --> filename
        return val.replace('\\\\','\\').replace('\\"','"')
    return val

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

##############################################################################
################################## Multipart ##################################
##############################################################################

def tob(data, enc='utf8'): # Convert strings to bytes (py2 and py3)
    return data.encode(enc) if isinstance(data, unicode) else data

def copy_file(stream, target, maxread=-1, buffer_size=2*16):
    ''' Read from :stream and write to :target until :maxread or EOF. '''
    size, read = 0, stream.read
    while 1:
        to_read = buffer_size if maxread < 0 else min(buffer_size, maxread-size)
        part = read(to_read)
        if not part: return size
        target.write(part)
        size += len(part)


class MultipartError(ValueError): pass


class MultipartParser(object):
    
    def __init__(self, stream, boundary, content_length=-1,
                 disk_limit=2**30, mem_limit=2**20, memfile_limit=2**18,
                 buffer_size=2**16):
        ''' Parse a multipart/form-data byte stream. This object is an iterator
            over the parts of the message.
            
            :param stream: A file-like stream. Must implement ``.read(size)``.
            :param boundary: The multipart boundary as a byte string.
            :param content_length: The maximum number of bytes to read.
        '''
        self.stream, self.boundary = stream, boundary
        self.content_length = content_length
        self.disk_limit = disk_limit
        self.memfile_limit = memfile_limit
        self.mem_limit = min(mem_limit, self.disk_limit)
        self.buffer_size = min(buffer_size, self.mem_limit)
        if self.buffer_size - 5 < len(boundary): # "--boundary--\n"
            raise MultipartError('Boundary does not fit into buffer_size.')
        self._done = []
        self._part_iter = None
    
    def __iter__(self):
        ''' Iterate over the parts of the multipart message. '''
        if not self._part_iter:
            self._part_iter = self._iterparse()
        for part in self._done:
            yield part
        for part in self._part_iter:
            self._done.append(part)
            yield part
    
    def parts(self):
        ''' Returns a list with all parts of the multipart message. '''
        return list(iter(self))
    
    def get(self, name, default=None):
        ''' Return the first part with that name. '''
        for part in self:
            if name == part.name:
                return part
        return default
    
    def _lineiter(self):
        ''' Iterate over a binary file-like object line by line. Each line is
            returned as a (line, line_ending) tuple. If the line does not fit
            into self.buffer_size, line_ending is empty and the rest of the line
            is returned with the next iteration.
        '''
        read = self.stream.read
        maxread, maxbuf = self.content_length, self.buffer_size
        while 1:
            lines = read(maxbuf if maxread < 0 else min(maxbuf, maxread))
            maxread -= len(lines)
            if not lines: break
            for line in lines.splitlines(True):
                if line[-2:] == '\r\n': yield line[:-2], '\r\n'
                elif line[-1:] == '\n': yield line[:-1], '\n'
                # elif line[-1:] == '\r': yield line[:-1], '\r'
                # Not supported. maxbuf could cut between \r and \n
                else:                   yield line, ''
     
    def _iterparse(self):
        lines, line = self._lineiter(), ''
        separator, terminator = '--'+self.boundary, '--'+self.boundary+'--'
        # Consume first boundary. Ignore leading blank lines
        for line, nl in lines:
            if line: break
        if line != separator:
            raise MultipartError("Stream does not start with boundary")
        # For each part in stream...
        mem_used, disk_used = 0, 0 # Track used resources to prevent DoS
        is_tail = False # True if the last line was incomplete (cutted)
        opts = {'buffer_size': self.buffer_size,
                'memfile_limit': self.memfile_limit}
        part = MultipartPart(**opts)
        for line, nl in lines:
            if line == terminator and not is_tail:
                part.file.seek(0)
                yield part
                break
            elif line == separator and not is_tail:
                if part.is_buffered(): mem_used  += part.size
                else:                  disk_used += part.size
                part.file.seek(0)
                yield part
                part = MultipartPart(**opts)
            else:
                is_tail = not nl # The next line continues this one
                part.feed(line, nl)
                if part.is_buffered():
                    if part.size + mem_used > self.mem_limit:
                        raise MultipartError("Memory limit reached.")
                elif part.size + disk_used > self.disk_limit:
                    raise MultipartError("Disk limit reached.")
        if line != terminator:
            raise MultipartError("Unexpected end of multipart stream.")
            

class MultipartPart(object):
    
    def __init__(self, buffer_size=2**16, memfile_limit=2**18):
        self.headerlist = []
        self.headers = Headers(self.headerlist)
        self.file = False
        self.size = 0
        self._buf = ''
        self.disposition, self.name, self.filename = None, None, None
        self.content_type, self.charset = None, None
        self.memfile_limit = memfile_limit
        self.buffer_size = buffer_size

    def feed(self, line, nl=''):
        if self.file:
            return self.write_body(line, nl)
        return self.write_header(line, nl)

    def write_header(self, line, nl):
        line = line.decode(self.charset or 'latin9')
        if not nl: raise MultipartError('Unexpected end of line in header.')
        if not line.strip(): # blank line -> end of header segment
            self.finish_header()
        elif line[0] in ' \t' and self.headerlist:
            name, value = self.headerlist.pop()
            self.headerlist.append((name, value+line.strip()))
        else:
            if ':' not in line:
                raise MultipartError("Syntax error in header: No colon.")
            name, value = line.split(':', 1)
            self.headerlist.append((name.strip(), value.strip()))

    def write_body(self, line, nl):
        if not line and not nl: return # This does not even flush the buffer
        self.size += len(line) + len(self._buf)
        self.file.write(self._buf + line)
        self._buf = nl
        if self.content_length > 0 and self.size > self.content_length:
            raise MultipartError('Size of body exceeds Content-Length header.')
        if self.size > self.memfile_limit and isinstance(self.file, io.BytesIO):
            self.file, old = TemporaryFile(mode='w+b'), self.file
            old.seek(0)
            copy_file(old, self.file, self.size, self.buffer_size)

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
        pos = self.file.tell()
        self.file.seek(0)
        val = self.file.read()
        self.file.seek(pos)
        return val
    
    def save_as(self, path):
        self.file.seek(0)
        with open(path, 'wb') as fp:
            size = copy_file(self.file, fp)
        return size

##############################################################################
#################################### WSGI ####################################
##############################################################################

def parse_form_data(environ, charset='utf8', strict=False, **kw):
    ''' Parse form data from an environ dict and return two :class:`MultiDict`
        instances. The first contains form fields with unicode keys and values.
        The second contains file uploads with unicode keys and
        :class:`MultipartPart` instances as values. Catch
        :exc:`ValueError` and :exc:`IndexError` to be sure.
        
        :param environ: An WSGI environment dict.
        :param charset: The charset to use if unsure. (default: utf8)
        :param strict: If True, raise :exc:`MultipartError` on parsing errors.
                       These are silently ignored by default.
    '''
        
    forms, files = MultiDict(), MultiDict()
    try:
        if environ.get('REQUEST_METHOD','GET').upper() not in ('POST', 'PUT'):
            raise MultipartError("Request method other than POST or PUT.")
        content_length = int(environ.get('CONTENT_LENGTH', '-1'))
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
            for part in MultipartParser(stream, boundary, content_length, **kw):
                codec = part.charset or charset
                name = part.name.decode(codec) if part.name else None
                if part.filename:
                    files[name] = part
                elif part.is_buffered():
                    forms[name] = part.value.decode(codec)
        elif content_type in ('application/x-www-form-urlencoded',
                              'application/x-url-encoded'):
            if content_length > MultipartParser.mem_limit:
                raise MultipartError("Request to big. Increase MAXMEM.")
            data = stream.read(MultipartParser.mem_limit).decode(charset)
            for key, value in urlparse.parse_qs(data, keep_blank_values=True):
                forms[key] = value
        else:
            raise MultipartError("Unsupported content type.")
    except MultipartError:
        if strict: raise
    return forms, files

