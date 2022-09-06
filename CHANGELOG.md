# Changelog

We are currently working on porting this changelog to the specifications in
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Version 0.1.3 - Unreleased


## Version 0.1.3 - Released 2022-09-05

### Fixed:
* Bug in serial queue when a dependency was None


## Version 0.1.2 - Released 2022-07-27

### Added
* Improved textual monitor for tmux queue
* Keep track of skipped jobs in tmux / serial queue
* The tmux queue can now clean up other existing sessions if you start fresh
* Basic airflow queue.

### Changed
* Job dependencies can now be given by name.

## Version 0.1.1 - Released 2022-07-27

### Fixed
* Bug where serial queue would execute jobs if any dependency passed.
* Minor dependency issues

## [Version 0.1.0] - Released

### Added
* Initial version
