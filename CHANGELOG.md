# Changelog

We are currently working on porting this changelog to the specifications in
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Version 0.2.3 - Unreleased

### Fixed
* Issue with slurm 21.x


## Version 0.2.2 - Released 2025-02-19

### Added

* Add initial support for monitoring passed and failed jobs in slurm.


### Fixed

* Fixed compatibility issues with Slurm v23


## Version 0.2.1 - Released 2024-11-18

### Added
* Slurmify helper script
* Better slurm support

### Fixed
* fix `SlurmQueue.is_available` with slurm version 19.x


## Version 0.2.0 - Released 2024-06-27

### Added
* Add "gpus" as a CLI option

### Changed
* Made pint an optional requirement

### Removed

* Drop support for 3.6 and 3.7


## Version 0.1.20 - Released 2024-03-19


## Version 0.1.19 - Released 2024-02-01

### Fixed
* Fixed issue with single-argv commands in the bash interface


## Version 0.1.18 - Released 2023-08-09

### Changed

* CLI Boilerplate run-queue can now pass kwargs to the run method.


## Version 0.1.17 - Released 2023-07-07

### Changed
* Change the CLI to be modal


## Version 0.1.16 - Released 2023-06-22

### Changed:
* Added experimental `vertical_chains` argument to draw-network-text 


## Version 0.1.15 - Released 2023-06-15

### Added
* Add yes argument to CLI

### Changed
* Added more options to the serial queue `run` method.


## Version 0.1.14 - Released 2023-05-11


## Version 0.1.13 - Released 2023-05-11


## Version 0.1.12 - Released 2023-04-18

### Fixed
* allow workaround gres issue with slurm by explicitly specifying it.


### Changed
* consolidated print commands code, all backends use the same logic now.


## Version 0.1.11 - Released 2023-04-13

### Fixed
* Issue with `slurm_options`

## Version 0.1.10 - Released 2023-04-11

### Added
* the `cli_boilerplate` submodule for help writing consistent scriptconfig + cmdqueue CLIs
* util yaml


## Version 0.1.9 - Released 2023-04-04

### Added
* Support for more sbatch options in slurm backend

### Fixed
* Bugs in slurm backend


## Version 0.1.8 - Released 2023-03-05

### Added:
* New experimental CLI-queue feature. Create a pipeline in bash using the CLI.
  Very basic atm.

### Changed
* The log option to submit now default to False (due to non-obvious tee issues)

### Fixed:
* The serial queue now correctly reorders jobs into a topological order when necessary.

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

