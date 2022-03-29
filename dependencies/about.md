packaged using instructions from here:


    https://realpython.com/pypi-publish-python-package/

    generally:

    python setup.py sdist bdist_wheel

    I have used "python3" instead, at the main directory

I have hardcoded dependencies from osm2geojson, that are:
    
    https://github.com/ideditor/id-area-keys/tree/446d771e6794fcc6091215f5849088b018289f74 (ISC Licence)

    https://github.com/tyrasd/osm-polygon-features/tree/65e0a1e290675877e8cdd007efcefc35a7dfe0dc (CC0-1.0-License)

you can also try to install it before the plugin installation using:

    <qgis_python_executable> -m pip install osm2geojson

# thank you  all osm2geojson authors: https://github.com/aspectumapp/osm2geojson/graphs/contributors 
