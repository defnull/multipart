=============
API Reference
=============

.. py:currentmodule:: multipart

SansIO Parser
=============

.. autoclass:: PushMultipartParser
    :members:

.. autoclass:: MultipartSegment
    :members:

Stream Parser
=============

.. autoclass:: MultipartParser
    :members:

.. autoclass:: MultipartPart
    :members:

WSGI Helper
===========

.. autofunction:: is_form_request
.. autofunction:: parse_form_data

Header utils
============

.. autofunction:: parse_options_header
.. autofunction:: header_quote
.. autofunction:: header_unquote 
.. autofunction:: content_disposition_quote
.. autofunction:: content_disposition_unquote


Exceptions
==========


.. autoexception:: MultipartError

.. autoexception:: ParserError

.. autoexception:: StrictParserError

.. autoexception:: ParserLimitReached

.. autoexception:: ParserStateError