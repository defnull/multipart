=========
Changelog
=========

This project follows Semantic Versioning (``major.minor.patch``), with the
exception that behavior changes are allowed in minor releases as long as the
change corrects behavior to match documentation, specification or
expectation. In other words: Bugfixes do not count as backward incompatible
changes, even if they technically change behavior from *incorrect* to *correct*
and may break applications that rely on *incorrect* or *undefined* behavior or
*undocumented* APIs.

Release 1.3
===========

**Not released yet**

* feat: New convenience methods :meth:`PushMultipartParser.parse_blocking` and
  :meth:`PushMultipartParser.parse_async`.
* feat: Nicer error messages when reading from a closed ``MultipartPart``.
* change: ``segment`` is now a required constructor argument for ``MultipartPart``
  and changed position. The constructor is not part of the public API, so this
  should not break user code.

Release 1.2
===========

This release improves error handling, documentation and performance, fixes
several parser edge-cases and adds new functionality. API changes are backwards
compatible.

* feat: Split up ``MultipartError`` into more specific exceptions and add HTTP
  status code hints. All exceptions are subclasses of ``MultipartError``.
* feat: New ``parse_form_data(ignore_errors)`` parameter to throw exceptions in
  non-strict mode, or suppress exceptions in strict mode. Default behavior does
  not change (throw in strict-mode, ignore in non-strict mode).
* feat: New ``is_form_request(environ)`` helper.
* feat: New specialized ``content_disposition_[un]quote`` functions.
* feat: ``parse_options_header()`` can now use different unquote functions. The
  default does not change.
* fix: ``parse_form_data()`` no longer checks the request method and the new
  ``is_form_request`` function also ignores it. All methods can carry parse-able
  form data, including unknown methods. The only reliable way is to check the
  ``Content-Type`` header, which both functions do.
* fix: First boundary not detected if separated by chunk border.
* fix: Allow CRLF in front of first boundary, even in strict mode.
* fix: Fail fast if first boundary is broken or part of the preamble.
* fix: Fail if stream ends without finding any boundary at all.
* fix: Use modern WHATWG quoting rules for field names and filenames (#60).
  Legacy quoting is still supported as a fallback.
* fix: ``MultiDict.get(index=999)`` should return default value, not throw IndexError.
* docs: Lots of work on docs and docstrings.
* perf: Multiple small performance improvements
* build: Require Python 3.8

Release 1.1
===========

This release could have been a patch release, but some of the fixes include
change in behavior to match documentation or specification. None of them should
be a surprise or have an impact on real-world clients, though. Existing apps
should be able to upgrade without issues.

* fix: Fail faster on input with invalid line breaks (#55)
* fix: Allow empty segment names (#56)
* fix: Avoid ResourceWarning when using parse_form_data (#57)
* fix: MultipartPart now always has a sensible content type.
* fix: Actually check parser state on context manager exit.
* fix: Honor Content-Length header, if present.
* perf: Reduce overhead for small segments (-21%)
* perf: Reduce write overhead for large uploads (-2%)

Release 1.0
===========

This release introduces a completely new, fast, non-blocking  ``PushMultipartParser``
parser, which now serves as the basis for all other parsers.

* feat: new ``PushMultipartParser`` parser.
* change: Parser is stricter by default and now rejects clearly broken input.
  This should not affect data sent by actual browsers or HTTP clients, but may break some artificial unit tests.
  * Fail on invalid line-breaks in headers or around boundaries.
  * Fail on invalid header names.
* change: Default charset for segment headers and text fields changed to ``utf8``, as recommended by W3C HTTP.
* change: Default disk and memory limits for ``MultipartParser`` increased, but multiple other limits were introduced to allow finer control. Check if the new defaults still fit your needs.
* change: Several undocumented APIs were deprecated or removed, some of which were not strictly private but should only be used by the parser itself, not by applications.

Release 0.2
===========

This release dropped support for Python versions below ``3.6``. Stay on ``multipart-0.1`` if you need Python 2.5+ support.

Patch 0.2.5
-----------

* security: Don't test semicolon separators in urlencoded data (#33)
* build: Add python-requires directive, indicating Python 3.5 or later is required and preventing older Pythons from attempting to download this version (#32)
* fix: Add official support for Python 3.10-3.12 (#38, #48)
* fix: Default value of ``copy_file`` should be ``2 ** 16``, not ``2 * 16`` (#41)
* docs: Update URL for Bottle (#42)

Patch 0.2.4
-----------

* fix: Consistently decode non-utf8 URL-encoded form-data

Patch 0.2.3
-----------

* fix: Import MutableMapping from collections.abc (#23)
* fix: Allow stream to contain data before first boundary (#25)
* tests: Fix a few more ResourceWarnings in the test suite (#24)

Patch 0.2.2
-----------

* fix: ResourceWarnings on Python 3 (#21)

Patch 0.2.1
-----------

* fix: empty payload (#20)


Release 0.1
===========

First release
