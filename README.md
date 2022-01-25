# sidewalkreator
Plugin designated to create the Geometries of Sidewalks (separated from streets) based on OpenStreetMap Streets.


The summary of what the plugin does is what follows:

  - Download and prepare the data (highways and optionally buildings) for a polygon of interest;
  - Provide some tools for highway selection and sidewalk parametrization;
  - Effectively draw the sidewalks
  - Draw the crossings (as sidewalks are required to be integrated to other highways in order to do routing) and kerb-crossing points (where the access ramp information may be filled)
  - Split sidewalk geometries into segments (including the option to not split at all), since in Brazil is very common that in front of each house there's a completely different sidewalk in comparison to the adjacent neighbors 😥.
  - Export the generated sidewalks, crossings and kerb points to a JOSM ready format, where all the importing into OSM shall be done.

It is mostly intended for Acessibility Mapping.
