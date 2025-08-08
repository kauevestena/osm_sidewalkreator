# OSM SIDEWALKREATOR

[A Qgis plugin, officialy available at the official Plugin Repository!](https://plugins.qgis.org/plugins/osm_sidewalkreator/)


<img src="assets/logos/sidewalkreator_logo.png" alt="Image" width="400">


## Scientific Publication is now Available!!

[Since 12/12/2023, in the European Journal of Geography:](https://eurogeojournal.eu/index.php/egj/article/view/553)

> de Moraes Vestena, Kauê, Silvana Philippi Camboim, and Daniel Rodrigues dos Santos. 2023. “OSM Sidewalkreator: A QGIS Plugin for an Automated Drawing of Sidewalk Networks for OpenStreetMap”. European Journal of Geography 14 (4):66-84. https://doi.org/10.48088/ejg.k.ves.14.4.066.084.

The experiments for the publication were carried out in a separate repository: https://github.com/kauevestena/sidewalk_analysis

## Article on OSM Wiki:

Please check it at: https://wiki.openstreetmap.org/wiki/OSM_SidewalKreator 

The wiki will speak about the workflow in a deep level of detail (still in progress).

## Presented at State of the Map 2022!
Abstract at the proceedings: https://zenodo.org/record/7004523

[Presentation slides](https://rebrand.ly/kauevestena_sotm22) 

[Recording](https://www.youtube.com/watch?v=B--1ge42UHY)

## sidewalkreator
Plugin designated to create the Geometries of Sidewalks (separated from streets) based on OpenStreetMap Streets.


[there's a tutorial with the basics on youtube:](https://www.youtube.com/watch?v=jq-K3Ixx0IM)

[and a mute video about the first importing at JOSM](https://www.youtube.com/watch?v=Apqdb73lNvY)

The summary of what the plugin does is what follows:

  - Download and prepare the data (highways and optionally buildings) for a polygon of interest;
  - Provide some tools for highway selection and sidewalk parametrization;
  - Effectively draw the sidewalks
  - Draw the crossings (as sidewalks are required to be integrated to other highways in order to do routing) and kerb-crossing points (where the access ramp information may be filled)
  - Split sidewalk geometries into segments (including the option to not split at all), since in Brazil, and some other places, is very common that in front of each house there's a completely different sidewalk in comparison to the adjacent neighbors 😥.
  - Export the generated sidewalks, crossings and kerb points to a JOSM ready format, where all the importing into OSM shall be done.

It is mostly intended for Acessibility Mapping.

Though the data was generated thinking on the usage for OSM, one may use it for pedestrian network analysis out-of-the-box, or even for other purposes inside or outside QGIS.

## Running tests with Docker

The project provides a Docker setup so tests can be executed inside a containerized QGIS environment.

### Build the image

```bash
docker build -t osm_sidewalkreator-tests .
```

### Run the tests

Mount the current project directory into the container and execute the test suite:

```bash
./scripts/run_qgis_tests.sh
# or to test a packaged release
./scripts/run_qgis_tests.sh --use-release
```

This helper script is equivalent to running the image directly:

```bash
docker run --rm -v "$(pwd)":/app osm_sidewalkreator-tests
```

Both approaches install Python dependencies from `requirements.txt` and run `pytest` within the QGIS image.

### Run processing algorithms

The `scripts/run_qgis_processing.sh` helper invokes QGIS Processing algorithms
from this plugin inside the same containerized environment. It mirrors the
`--use-release` flag of the test script so algorithms can be executed from the
source tree or a built release ZIP.

Run an algorithm against the source tree:

```bash
./scripts/run_qgis_processing.sh generateprotoblocksfromosm INPUT=/path/to/input.geojson OUTPUT=/tmp/out.gpkg
```

Or run it using a release build:

```bash
./scripts/run_qgis_processing.sh --use-release generateprotoblocksfromosm INPUT=/path/to/input.geojson OUTPUT=/tmp/out.gpkg
```

## Creating a release package

The script `release/release_zip.py` bundles the plugin into a ZIP archive for distribution. By default it packages the current repository and writes `osm_sidewalkreator.zip` under `~/sidewalkreator_release`:

```bash
python release/release_zip.py
```

You can customize the plugin source, output directory and excluded files:

```bash
python release/release_zip.py --plugin-dir /path/to/plugin \
  --output-dir /tmp/build --exclude tests docs "*.pyc"
```

The `--exclude` option accepts multiple patterns either separated by spaces or by repeating the flag.
