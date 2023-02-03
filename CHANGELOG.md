# Changelog

We are currently working on porting this changelog to the specifications in
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Version 0.1.8 - Unreleased

### Added:
* New experimental CLI-queue feature. Create a pipeline in bash using the CLI.
  Very basic atm.

## Version 0.1.7 - Released 2023-01-28

### Added:
* Experimental CLI to help cleanup dangling tmux jobs

### Deprecated
* Deprecate `rprint` in favor of `print_commands`.
* Deprecate `use_rich` in `print_commands` in favor of `style='rich'`.

### Changed
* Tweaked text output
* Demo in the readme with better record demo scripts


## Version 0.1.6 - Released 2023-01-16

### Added:
* new `other_session_handler` arg to run, which can be ask, kill, ignore, or auto.

### Fixed:
* Textual monitor will now restart if you decide not to quit.

### Changed:
* tmux queue is condensed when size=1


## Version 0.1.5 - Released 2022-12-15

### Added
* UnknownBackendError and DuplicateJobError
* Add `tags` property to Jobs and `exclude_tags` to `rprint`.


## Version 0.1.4 - Released 2022-10-31

### Changed
* The kill-other-session logic now only asks to kill sessions with the same
  name.

* The serial / tmux queue now output stdout/stderr of each process to a log
  file and write a status indicating when a command has started to run.

* Slurm is available check now looks to see if any node exists that is not down.


## Version 0.1.3 - Released 2022-09-05


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

