Change Log
==========

All notable changes to this project will be documented in this file.
This project adheres to `Semantic Versioning`_.

`Unreleased`_
-------------

`0.2.1`_ - 2015-06-11
---------------------

Fixed
~~~~~

- README formatting


`0.2.0`_ - 2015-06-11
---------------------

Added
~~~~~

- `#2`_ Added first tests.
  `@andre-luiz-dos-santos`_

Changed
~~~~~~~

- Make write\_sock more efficient, not sending byte by byte anymore.
  `@andre-luiz-dos-santos`_

Fixed
~~~~~

- Encoding of word length when sending words longer than 127.
- Error handling during SSL connection setup.

Removed
~~~~~~~

- Python 3.2/3.3 compatibility.

`0.1.2`_ - 2015-06-01
---------------------

Changed
~~~~~~~

- `#1`_ Return ID when adding new records.
  `@andre-luiz-dos-santos`_

Fixed
~~~~~

- Wrong LICENSE in setup.py

0.1.1 - 2015-05-08
------------------

Added
~~~~~

- initial public release

.. _Semantic Versioning: http://semver.org/
.. _Unreleased: https://github.com/vshn/tikapy/compare/v0.2.1...HEAD
.. _0.2.1: https://github.com/vshn/tikapy/compare/v0.2.0...v0.2.1
.. _0.2.0: https://github.com/vshn/tikapy/compare/v0.1.2...v0.2.0
.. _0.1.2: https://github.com/vshn/tikapy/compare/v0.1.1...v0.1.2
.. _#1: https://github.com/vshn/tikapy/pull/1
.. _#2: https://github.com/vshn/tikapy/pull/2
.. _@andre-luiz-dos-santos: https://github.com/andre-luiz-dos-santos
