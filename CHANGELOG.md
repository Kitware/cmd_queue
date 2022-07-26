# Changelog

We are currently working on porting this changelog to the specifications in
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Version 0.1.2 - Unreleased

### Added
* Improved textual monitor for tmux queue
* Keep track of skipped jobs in tmux / serial queue
* The tmux queue can now clean up other existing sessions if you start fresh

## Version 0.1.1 - Unreleased

### Fixed
* Bug where serial queue would execute jobs if any dependency passed.
* Minor dependency issues

## [Version 0.1.0] - Released

### Added
* Initial version



python -m watch.cli.coco_align_geotiffs --src /media/joncrall/raid/home/joncrall/data/dvc-repos/smart_watch_dvc/Uncropped-Drop4-2022-07-18-c10-TA1-S2-L8-ACC/data_US_C002_fielded.kwcoco.json --dst /media/joncrall/raid/home/joncrall/data/dvc-repos/smart_watch_dvc/Aligned-Drop4-2022-07-18-c10-TA1-S2-L8-ACC/imgonly-US_C002.kwcoco.json --regions /media/joncrall/raid/home/joncrall/data/dvc-repos/smart_watch_dvc/annotations/region_models/US_C002.geojson --context_factor=1 --geo_preprop=auto --keep=roi-img '--include_channels=blue|green|red|nir|swir16|swir22' --exclude_channels=None --visualize=False --debug_valid_regions=False --rpc_align_method affine_warp --verbose=0 --aux_workers=0 --workers=12
