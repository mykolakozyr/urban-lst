# Land Surface Temperature - World Urban Areas
The app enables discovering land surface temperature data over major urban areas. Click on the urban area of your interest and then on "Discover the Land Surface Temperature Data!"

Temporal extent: 2017-01-01 till today.


App is built on top of Google Earth Engine. For a selected urban area, the app calculates the mean land surface temperature value in a given area.


## References
* World Urban Areas - [ArcGIS Hub](https://hub.arcgis.com/datasets/schools-BE::world-urban-areas/explore).
* Land Surface Temperature - [MODIS via Google Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A2).
* Map rendering - [PyDeck](https://deckgl.readthedocs.io/en/latest/) within [streamlit-deckgl](https://pypi.org/project/streamlit-deckgl/0.5.1/).
* Library for visualizations - [Vega-Altair](https://altair-viz.github.io/index.html).
