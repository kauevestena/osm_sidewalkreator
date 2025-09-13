# Roadmap for implementing the **Draw Missing Crossings (BBOX)** algorithm

This roadmap explains how to implement the first task described in the repository’s `TODO` file, which asks for an algorithm that draws missing pedestrian crossings inside a bounding‑box (BBOX). The algorithm should reuse existing modules from the *osm\_sidewalkreator* codebase. The goal is to identify pairs of neighboring protoblock polygons that both contain existing sidewalks and ensure that missing crossings are drawn consistently.

---

## Step 1 – Set up a new processing provider algorithm

* Implement as a **QGIS Processing Provider algorithm**, not as part of the GUI.
* Add a new algorithm class (e.g., `DrawMissingCrossingsBBoxAlgorithm`) under the `processing/` directory.
* Register it in the provider so that it appears in the QGIS toolbox.
* Define required inputs: bounding box, OSM source, and parameters (e.g., minimum road width, crossing type).

---

## Step 2 – Generate protoblocks

* Reuse existing functions from `protoblock_bbox_algorithm.py`.
* Input: bounding box.
* Output: protoblock polygons with sidewalk existence information attached.

---

## Step 3 – Identify adjacent block pairs

For each protoblock polygon:

1. **Check adjacency** – Use existing geometry helpers from `generic_functions.py` to detect shared boundaries between blocks (if any, otherwise implement it).
2. **Check sidewalks** – Only keep pairs where **both blocks already have sidewalks** along the shared edge.
3. **Crossing status** –

   * If **both sides already have crossings**, skip this pair.
   * If **only one side has a crossing**, keep the pair and mark it as *missing crossing* on the other side.

---

## Step 4 – Search for existing crossings in OSM

* Use `osm_fetch.py` functions to query the Overpass API.
* Define a search radius as **half the shared edge length**.
* Collect crossing features tagged with `highway=crossing`.
* Associate found crossings with the correct shared segment.

---

## Step 5 – Generate new crossing geometries

* For missing crossings:

  * Generate a line across the shared segment.
  * Add kerb points at both ends, using parameter rules from `parameters.py` (e.g., kerb type).
* Ensure geometries align with existing node/edge structure.

---

## Step 6 – Integration with existing algorithms

* Follow the style of `full_sidewalkreator_bbox_algorithm.py` for data structures.
* Log metadata about crossings (new, existing, skipped) for reporting.

---

## Step 7 – Export and testing

* Allow export of results to GeoPackage/GeoJSON.
* Add unit tests (using Docker, place at docker/tests/missing_crossings ) for:

  * Detection of adjacency.
  * Handling of cases where one side already has a crossing.
  * Correct geometry generation.
  * Full run creating a docker/run_missing_crossings.sh (similar to docker/run_protoblocks_bbox.sh)
    sample bbox (there are positive cases of missing crossings, that can change over time, since OSM data is dynamic): 

        `bbox = {
            "min_lon": -49.289753,
            "min_lat": -25.466447,
            "max_lon": -49.284410,
            "max_lat": -25.462165
        }`


* Finally, validate results visually in QGIS.

---

## Step 8 – Documentation

* Update `README.md` with a new section for **Draw Missing Crossings (BBOX)**.
* Document input parameters, algorithm logic, and limitations.
* Provide a small test dataset for reproducibility.

---

## Dependencies and Considerations

* Relies on: `protoblock_bbox_algorithm.py`, `generic_functions.py`, `osm_fetch.py`, `parameters.py`.
* Needs reliable OSM fetching (consider caching results).
* Must handle topology carefully to avoid duplicate crossings.

---

✅ With this roadmap, the algorithm can be implemented systematically, integrated into the processing framework, and tested for robustness.
