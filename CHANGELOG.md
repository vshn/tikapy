# Change Log
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased][unreleased]

### Added
- Added first tests.
  [@andre-luiz-dos-santos](https://github.com/andre-luiz-dos-santos)

### Changed
- Make write_sock more efficient, not sending byte by byte anymore.
  [@andre-luiz-dos-santos](https://github.com/andre-luiz-dos-santos)

### Fixed
- Encoding of word length when sending words longer than 127.
- Error handling during SSL connection setup.

### Removed
- Python 3.2/3.3 compatibility.

## [0.1.2] - 2015-06-01

### Changed
- [#1](https://github.com/vshn/tikapy/pull/1) Return ID when adding new records 
  [@andre-luiz-dos-santos](https://github.com/andre-luiz-dos-santos)

### Fixed
- Wrong LICENSE in setup.py

## 0.1.1 - 2015-05-08

### Added
- initial public release

[unreleased]: https://github.com/vshn/tikapy/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/vshn/tikapy/compare/v0.1.1...v0.1.2
