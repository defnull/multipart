=============
API Reference
=============

.. py:currentmodule:: multipart

.. automodule:: multipart

SansIO Parser
=============

.. autoclass:: PushMultipartParser
    :members:

.. autoclass:: MultipartSegment
    :members:
    :special-members: __getitem__

Stream Parser
=============


.. autoclass:: MultipartParser
    :members:
    :special-members: __iter__, __getitem__


.. autoclass:: MultipartPart
    :members:

WSGI Helper
===========

.. autofunction:: is_form_request
.. autofunction:: parse_form_data

.. autoclass:: MultiDict
    :members:

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