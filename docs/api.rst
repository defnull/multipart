=============
API Reference
=============

.. py:currentmodule:: multipart

.. automodule:: multipart

Non-Blocking Parser
===================

.. autoclass:: PushMultipartParser
    :members:
    :special-members: __enter__, __exit__

.. autoclass:: MultipartSegment
    :members:
    :special-members: __getitem__


Buffered Parser
===============


.. autoclass:: MultipartParser
    :members:
    :special-members: __iter__, __getitem__


.. autoclass:: MultipartPart
    :members:


WSGI Helper
===========

.. autofunction:: is_form_request
.. autofunction:: parse_form_data


Header parsing
==============

.. autofunction:: parse_options_header
.. autofunction:: header_quote
.. autofunction:: header_unquote 
.. autofunction:: content_disposition_quote
.. autofunction:: content_disposition_unquote


Utilities
=========

.. autoclass:: MultiDict
    :members:


Exceptions
==========


.. autoexception:: MultipartError
    :exclude-members: __init__, __new__

.. autoexception:: ParserError
    :exclude-members: __init__, __new__

.. autoexception:: StrictParserError
    :exclude-members: __init__, __new__

.. autoexception:: ParserLimitReached
    :exclude-members: __init__, __new__

.. autoexception:: ParserStateError
    :exclude-members: __init__, __new__
