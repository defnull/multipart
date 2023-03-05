# -*- coding: utf-8 -*-
"""
Parser for multipart/form-data
==============================

This module provides a parser for the multipart/form-data format. It can read
from a file, a socket or a WSGI environment. The parser can be used to replace
cgi.FieldStorage to work around its limitations.
"""


__author__ = "Marcel Hellkamp"
__version__ = "0.2.4"
__license__ = "MIT"
__all__ = ["MultipartError", "MultipartParser", "MultipartPart", "AsyncMultipartParser", "MultipartBuffer", "parse_form_data"]


import re
from io import BytesIO
from tempfile import TemporaryFile
from typing import Iterator, Optional, Union
from urllib.parse import parse_qs
from wsgiref.headers import Headers
from collections.abc import MutableMapping as DictMixin


##############################################################################
################################ Helper & Misc ###############################
##############################################################################
# Some of these were copied from bottle: http://bottle.paws.de/


# ---------
# MultiDict
# ---------


class MultiDict(DictMixin):
    """ A dict that remembers old values for each key.
        HTTP headers may repeat with differing values,
        such as Set-Cookie. We need to remember all
        values.
    """

    def __init__(self, *args, **kwargs):
        self.dict = dict()
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def __len__(self):
        return len(self.dict)

    def __iter__(self):
        return iter(self.dict)

    def __contains__(self, key):
        return key in self.dict

    def __delitem__(self, key):
        del self.dict[key]

    def keys(self):
        return self.dict.keys()

    def __getitem__(self, key):
        return self.get(key, KeyError, -1)

    def __setitem__(self, key, value):
        self.append(key, value)

    def append(self, key, value):
        self.dict.setdefault(key, []).append(value)

    def replace(self, key, value):
        self.dict[key] = [value]

    def getall(self, key):
        return self.dict.get(key) or []

    def get(self, key, default=None, index=-1):
        if key not in self.dict and default != KeyError:
            return [default][index]

        return self.dict[key][index]

    def iterallitems(self):
        for key, values in self.dict.items():
            for value in values:
                yield key, value


def to_bytes(data, enc="utf8"):
    if isinstance(data, str):
        data = data.encode(enc)

    return data


def copy_file(stream, target, maxread=-1, buffer_size=2 ** 16):
    """ Read from :stream and write to :target until :maxread or EOF. """
    size, read = 0, stream.read

    while True:
        to_read = buffer_size if maxread < 0 else min(buffer_size, maxread - size)
        part = read(to_read)

        if not part:
            return size

        target.write(part)
        size += len(part)


# -------------
# Header Parser
# -------------


_special = re.escape('()<>@,;:"\\/[]?={} \t')
_re_special = re.compile(r'[%s]' % _special)
_quoted_string = r'"(?:\\.|[^"])*"'  # Quoted string
_value = r'(?:[^%s]+|%s)' % (_special, _quoted_string)  # Save or quoted string
_option = r'(?:;|^)\s*([^%s]+)\s*=\s*(%s)' % (_special, _value)
_re_option = re.compile(_option)  # key=value part of an Content-Type like header


def header_quote(val):
    if not _re_special.search(val):
        return val

    return '"' + val.replace("\\", "\\\\").replace('"', '\\"') + '"'


def header_unquote(val, filename=False):
    if val[0] == val[-1] == '"':
        val = val[1:-1]

        if val[1:3] == ":\\" or val[:2] == "\\\\":
            val = val.split("\\")[-1]  # fix ie6 bug: full path --> filename

        return val.replace("\\\\", "\\").replace('\\"', '"')

    return val


def parse_options_header(header, options=None):
    if ";" not in header:
        return header.lower().strip(), {}

    content_type, tail = header.split(";", 1)
    options = options or {}

    for match in _re_option.finditer(tail):
        key = match.group(1).lower()
        value = header_unquote(match.group(2), key == "filename")
        options[key] = value

    return content_type, options


##############################################################################
################################## Multipart #################################
##############################################################################


class MultipartError(ValueError):
    pass


class MultipartParser(object):
    def __init__(
        self,
        stream,
        boundary,
        content_length=-1,
        disk_limit=2 ** 30,
        mem_limit=2 ** 20,
        memfile_limit=2 ** 18,
        buffer_size=2 ** 16,
        charset="latin1",
    ):
        """ Parse a multipart/form-data byte stream. This object is an iterator
            over the parts of the message.

            :param stream: A file-like stream. Must implement ``.read(size)``.
            :param boundary: The multipart boundary as a byte string.
            :param content_length: The maximum number of bytes to read.
        """
        self.stream = stream
        self.boundary = boundary
        self.content_length = content_length
        self.disk_limit = disk_limit
        self.memfile_limit = memfile_limit
        self.mem_limit = min(mem_limit, self.disk_limit)
        self.buffer_size = min(buffer_size, self.mem_limit)
        self.charset = charset

        if self.buffer_size - 6 < len(boundary):  # "--boundary--\r\n"
            raise MultipartError("Boundary does not fit into buffer_size.")

        self._done = []
        self._part_iter = None

    def __iter__(self):
        """ Iterate over the parts of the multipart message. """
        if not self._part_iter:
            self._part_iter = self._iterparse()

        for part in self._done:
            yield part

        for part in self._part_iter:
            self._done.append(part)
            yield part

    def parts(self):
        """ Returns a list with all parts of the multipart message. """
        return list(self)

    def get(self, name, default=None):
        """ Return the first part with that name or a default value (None). """
        for part in self:
            if name == part.name:
                return part

        return default

    def get_all(self, name):
        """ Return a list of parts with that name. """
        return [p for p in self if p.name == name]

    def _iterparse(self):
        read = self.stream.read
        maxbuf = self.buffer_size
        mem_used = disk_used = 0
        opts = {
            "buffer_size": self.buffer_size,
            "memfile_limit": self.memfile_limit,
            "charset": self.charset,
        }

        part = None

        with AsyncMultipartParser(self.boundary, self.content_length) as parser:
            while not parser.end:
                for chunk in parser.parse(read(maxbuf)):
                    if not part:
                        part = MultipartPart(**opts)
                        part.set_headers(chunk.headerlist)

                    part.write_body(chunk.drain())

                    if part.is_buffered():
                        if part.size + mem_used > self.mem_limit:
                            raise MultipartError("Memory limit reached.")
                    elif part.size + disk_used > self.disk_limit:
                        raise MultipartError("Disk limit reached.")

                    if chunk.complete:
                        if part.is_buffered():
                            mem_used += part.size
                        else:
                            disk_used += part.size
                        part.file.seek(0)
                        yield part
                        part = None               


class MultipartPart(object):
    def __init__(self, buffer_size=2 ** 16, memfile_limit=2 ** 18, charset="latin1"):
        self.headerlist = []
        self.headers = None
        self.file = BytesIO()
        self.size = 0
        self.disposition = None
        self.name = None
        self.filename = None
        self.content_type = None
        self.charset = charset
        self.memfile_limit = memfile_limit
        self.buffer_size = buffer_size

    def set_headers(self, headerlist):
        self.headerlist = headerlist
        self.headers = Headers(self.headerlist)
        content_disposition = self.headers.get("Content-Disposition", "")
        content_type = self.headers.get("Content-Type", "")

        if not content_disposition:
            raise MultipartError("Content-Disposition header is missing.")

        self.disposition, self.options = parse_options_header(content_disposition)
        self.name = self.options.get("name")
        self.filename = self.options.get("filename")
        self.content_type, options = parse_options_header(content_type)
        self.charset = options.get("charset") or self.charset
        self.content_length = int(self.headers.get("Content-Length", "-1"))

    def write_body(self, data):
        if not data:
            return

        self.size += len(data)
        self.file.write(data)

        if self.content_length > 0 and self.size > self.content_length:
            raise MultipartError("Size of body exceeds Content-Length header.")

        if self.size > self.memfile_limit and isinstance(self.file, BytesIO):
            # TODO: What about non-file uploads that exceed the memfile_limit?
            self.file, old = TemporaryFile(mode="w+b"), self.file
            old.seek(0)
            copy_file(old, self.file, self.size, self.buffer_size)

    def is_buffered(self):
        """ Return true if the data is fully buffered in memory."""
        return isinstance(self.file, BytesIO)

    @property
    def value(self):
        """ Data decoded with the specified charset """

        return self.raw.decode(self.charset)

    @property
    def raw(self):
        """ Data without decoding """
        pos = self.file.tell()
        self.file.seek(0)

        try:
            val = self.file.read()
        except IOError:
            raise
        finally:
            self.file.seek(pos)

        return val

    def save_as(self, path):
        with open(path, "wb") as fp:
            pos = self.file.tell()

            try:
                self.file.seek(0)
                size = copy_file(self.file, fp)
            finally:
                self.file.seek(pos)

        return size

    def close(self):
        if self.file:
            self.file.close()


class AsyncMultipartParser:
    def __init__(
        self,
        boundary: Union[str, bytes],
        content_length=-1,
        max_header_size=4096+128,
        max_header_count=128,
        charset="utf8",
        strict=False
    ):
        """ A non-blocking parser for multipart/form-data.

            This parser accepts chunks of data and yields zero or more
            MultipartBuffers for each chunk. Each MultipartBuffer contains
            all headers of a multipart segment and all binary data that was
            parsed so far an not drained yet. Incomplete MultipartBuffers are
            returned repeatedly until they are complete. It is the
            responsibility of the caller to do something with the binary data
            and 'drain' the buffers before they grow too large.

            Pseudocode::
                with AsyncMultipartParser('boundary') as parser:
                    tempfile = None
                    for chunk in read_from_socket():
                        for buffer in parser.push(chunk):
                            if not file:
                                tempfile = tempfile.NamedTemporaryFile()
                            tempfile.write(buffer.drain())
                            if buffer.completed:
                                tempfile.close()
                                do_something_with(tempfile)
                                tempfile = None

            :param boundary: The multipart boundary as a (byte) string.
            :param content_length: Maximum number of bytes to accept, or -1 for no limit.
            :param max_header_size: Maximum size of a single header (name+value).
            :param max_header_count: Maximum number of headers per part.
            :param charset: Charset for header names and values.
            :param strict: If true, be more picky about parsing.
        """
        self.boundary = to_bytes(boundary)
        self.content_length = content_length
        self.charset = charset
        self.max_header_size = max_header_size
        self.max_header_count = max_header_count
        self.strict = strict

        self.delimiter = b'--' + self.boundary
        self.buffer = bytearray()
        self.parsed = 0

        self.part : Optional[MultipartBuffer] = None
        self.end = False
        self.eof = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            self.close()

    def close(self):
        """ Raise MultipartError if the multipart stream is not complete yet. """
        if not self.end:
            raise MultipartError("Unexpected end of multipart stream (parser closed)")

    def parse(self, chunk: Union[bytes, bytearray]) -> Iterator["MultipartBuffer"]:
        """ 
            Parse a single chunk of data and yield MultipartBuffer instances.

            If not enough data is provided to complete a MultipartBuffer, the
            same MultipartBuffer will be returned again next time until it is
            complete. New data is appended to its internal buffer, so make sure
            to drain this buffer before it grows too large.

            Call with an empty chunk to singal end of stream.
        """

        buffer = self.buffer
        delimiter = self.delimiter
        blen = len(delimiter)

        buffer += chunk # Copy chunk to existing buffer
        offset = 0

        if self.eof:
            raise MultipartError("Unexpected data after end of multipart stream.")

        if self.end:
            if self.strict:
                raise MultipartError("Unexpected data after final multipart delimiter.")
            return # just ignore it

        if not len(chunk):
            self.eof = True

        if self.content_length > -1 and self.parsed + len(buffer) >= self.content_length:
            self.eof = True
            if self.parsed + len(buffer) > self.content_length:
                raise MultipartError("Unexpected data after Content-Length reached.")

        while True:
            # Begin by searching for the first delimiter and skip all data that
            # is infront of it. RFC 2046, section 5.1.1 allows a (useless) preamble.
            if not self.part:
                bi = buffer.find(delimiter, offset)

                if bi > -1:
                    tail = buffer[bi+blen:bi+blen+2]

                    # First delimiter found -> Start after it
                    if tail == b'\r\n':
                        offset = bi + blen + 2
                        self.part = MultipartBuffer()
                        continue

                    # First delimiter is final delimiter! -> Empty multipart stream
                    if tail == b'--':
                        offset = bi + blen + 2
                        self.end = True
                        break # Stop parsing

                # No delimiter found, skip data until we find one
                offset = len(buffer) - (blen + 4)
                break # wait for more data

            # There might be a partial delimiter at the end of our buffer, so stop
            # parsing and wait for more data if remaining buffer is smaller than a
            # full final delimiter.
            if len(buffer) - offset < blen + 4:
                break # wait for more data

            # Parse header section
            if self.part._size == -1:
                nl = buffer.find(b'\r\n', offset)

                # Incomplete header line -> wait for more data
                if nl == -1:
                    if len(buffer) - offset > self.max_header_size:
                        raise MultipartError("Malformed header: Too large")
                    break # wait for more data

                # Empty line -> end of header segment
                if nl == offset:
                    self.part._size = 0 # Mark as header-complete
                    offset += 2
                    continue

                # Line start with whitespace -> Header continuation
                if buffer[offset] in b' \t':
                    if self.strict:
                        raise MultipartError("Malformed header: Header Continuation is deprectaed in rfc7230")
                    if not self.part._headerlist:
                        raise MultipartError("Malformed header: First header cannot be a continuation")
                    name, value = self.part._headerlist.pop()
                    if len(name) + len(value) + nl - offset > self.max_header_size:
                        # TODO: name and old value are counted as glyphs, not bytes
                        raise MultipartError("Malformed header: Header too large (continuation)")
                    value += ' ' + buffer[offset+1:nl].decode(self.charset).strip()
                    self.part._headerlist.append((name, value))
                    offset = nl + 2
                    continue

                col = buffer.find(b':', offset, nl)
                if col == -1:
                    raise MultipartError("Malformed header: Expected ':', found CRLF")

                name  = buffer[offset:col].decode(self.charset).strip()
                value = buffer[col+1:nl].decode(self.charset).strip()
                if not name:
                    raise MultipartError("Malformed header: Empty name")
                self.part._headerlist.append((name, value))
                offset = nl + 2
                continue

            # We are in data segment of a part
            bi = buffer.find(b'\r\n' + delimiter, offset)
            if bi > -1:
                tail = buffer[bi+blen+2:bi+blen+4]
                if tail in (b'\r\n', b'--'):
                    # Delimiter found -> complete this chunk
                    self.part._append(buffer[offset:bi])
                    self.part._complete = True
                    yield self.part
                    offset = bi + blen + 4

                    # Normal delimiter
                    if tail == b'\r\n':
                        self.part = MultipartBuffer()
                        continue
                
                    # Final delimiter
                    self.part = None
                    self.end = True
                    break

            # No boundary found, or boundary was not an actual delimiter
            # Yield chunk, but keep enough to ensure we do not miss a partial boundary
            tail = blen + 3 # len(\r\nboundary\r\n) - 1
            self.part._append(buffer[offset:-tail])
            offset = len(buffer) - tail
            yield self.part
            break

        # We ran out of data, or reached the end
        if self.eof and not self.end:
            raise MultipartError("Unexpected end of multipart stream.")
        self.parsed += offset
        buffer[:] = buffer[offset:]



class MultipartBuffer:
    """
        A (partly) parsed multipart segment.
    """
    def __init__(self):
        self._headerlist = []
        self._headers: Optional[Headers] = None
        self._buffer = bytearray()
        self._size = -1
        self._complete = False

    def _append(self, data):
        if self._size < 0:
            self._size = 0
        if data:
            self._size += len(data)
            self._buffer += data

    @property
    def complete(self):
        return self._complete

    @property
    def incomplete(self):
        return not self._complete

    @property
    def buffersize(self):
        """ Current size of internal buffer """
        return len(self._buffer)

    @property
    def size(self):
        """ Total size of body content (so far) """
        return self._size

    @property
    def headerlist(self):
        return self._headerlist[:]

    @property
    def headers(self):
        if not self._headers:
            self._headers = Headers(self._headerlist)
        return self._headers

    def drain(self):
        """ Return the current internal buffer and replace it with an empty one. """
        tmp = self._buffer
        self._buffer = bytearray()
        return tmp


##############################################################################
#################################### WSGI ####################################
##############################################################################


def parse_form_data(environ, charset="utf8", strict=False, **kwargs):
    """ Parse form data from an environ dict and return a (forms, files) tuple.
        Both tuple values are dictionaries with the form-field name as a key
        (unicode) and lists as values (multiple values per key are possible).
        The forms-dictionary contains form-field values as unicode strings.
        The files-dictionary contains :class:`MultipartPart` instances, either
        because the form-field was a file-upload or the value is too big to fit
        into memory limits.

        :param environ: An WSGI environment dict.
        :param charset: The charset to use if unsure. (default: utf8)
        :param strict: If True, raise :exc:`MultipartError` on any parsing
                       errors. These are silently ignored by default.
    """

    forms, files = MultiDict(), MultiDict()

    try:
        if environ.get("REQUEST_METHOD", "GET").upper() not in ("POST", "PUT"):
            raise MultipartError("Request method other than POST or PUT.")
        content_length = int(environ.get("CONTENT_LENGTH", "-1"))
        content_type = environ.get("CONTENT_TYPE", "")

        if not content_type:
            raise MultipartError("Missing Content-Type header.")

        content_type, options = parse_options_header(content_type)
        stream = environ.get("wsgi.input") or BytesIO()
        kwargs["charset"] = charset = options.get("charset", charset)

        if content_type == "multipart/form-data":
            boundary = options.get("boundary", "")

            if not boundary:
                raise MultipartError("No boundary for multipart/form-data.")

            for part in MultipartParser(stream, boundary, content_length, **kwargs):
                if part.filename or not part.is_buffered():
                    files[part.name] = part
                else:  # TODO: Big form-fields are in the files dict. really?
                    forms[part.name] = part.value

        elif content_type in (
            "application/x-www-form-urlencoded",
            "application/x-url-encoded",
        ):
            mem_limit = kwargs.get("mem_limit", 2 ** 20)
            if content_length > mem_limit:
                raise MultipartError("Request too big. Increase MAXMEM.")

            data = stream.read(mem_limit).decode(charset)

            if stream.read(1):  # These is more that does not fit mem_limit
                raise MultipartError("Request too big. Increase MAXMEM.")

            data = parse_qs(data, keep_blank_values=True, encoding=charset)

            for key, values in data.items():
                for value in values:
                    forms[key] = value
        else:
            raise MultipartError("Unsupported content type.")

    except MultipartError:
        if strict:
            for part in files.values():
                part.close()
            raise

    return forms, files
