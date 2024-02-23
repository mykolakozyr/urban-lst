import streamlit as st
import json
import geojson
import ee
import pandas as pd
import geopandas as gpd
import altair as alt
from shapely.geometry import shape
import pydeck as pdk
from streamlit_deckgl import st_deckgl



MAP_EMOJI_URL = "https://em-content.zobj.net/source/apple/354/cityscape-at-dusk_1f306.png"

# Set page title and favicon.
st.set_page_config(
    page_title="Land Surface Temperature - World Urban Areas", 
    page_icon=MAP_EMOJI_URL,
    layout="wide"
)

col1, col2, col3 = st.columns([1, 4, 1])
# Display header.
col2.markdown("<br>", unsafe_allow_html=True)
col2.image(MAP_EMOJI_URL, width=80)
col2.markdown("""
    # Land Surface Temperature - World Urban Areas
    [![Follow](https://img.shields.io/twitter/follow/mykolakozyr?style=social)](https://www.twitter.com/mykolakozyr)
    [![Follow](https://img.shields.io/badge/LinkedIn-blue?style=flat&logo=linkedin&labelColor=blue)](https://www.linkedin.com/in/mykolakozyr/)
    
    ## Details

    The app enables discovering land surface temperature data over major urban areas. Click on the urban area of your interest and then on "Discover the Land Surface Temperature Data!" 

    Temporal extent: 2017-01-01 till today.

    ---
    """)

def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

def convert_gdf(gdf):
    gdf['geometry'] = gdf['geometry'].astype('geometry') 
    gdf['Timestamp'] = gdf['Timestamp'].astype(str)
    return gdf.to_json()


json_data = st.secrets["json_data"]
service_account = st.secrets["service_account"]

json_object = json.loads(json_data, strict=False)
json_object = json.dumps(json_object)
credentials = ee.ServiceAccountCredentials(service_account, key_data=json_object)
ee.Initialize(credentials)

import src.gee as gee

# Defining the temporal extent of the discovery
today = ee.Date(pd.to_datetime('today'))
date_range = ee.DateRange('2017-01-01', today)

# Building a map
DATA_URL = "data/urban_areas.geojson"
urban_areas = gpd.read_file(DATA_URL)

INITIAL_VIEW_STATE = pdk.ViewState(latitude=50, longitude=10, zoom=4, max_zoom=16, pitch=0, bearing=0)
geojson = pdk.Layer(
    "GeoJsonLayer",
    data=urban_areas,
    opacity=0.4,
    stroked=False,
    filled=True,
    extruded=True,
    wireframe=True,
    get_fill_color=[255, 0, 0],
    get_line_color=[255, 255, 255],
    # get_line_width=2,
    # line_width_units='pixels',
    auto_highlight=True,
    pickable=True,
)

with st.form(key='my_form'):
    r = pdk.Deck(
        layers=[geojson],
        tooltip = {
            "text": "Urban area: {Name}"
        }, 
        initial_view_state=INITIAL_VIEW_STATE)
    value = st_deckgl(r, height=500, events=['click'])
    #st.write('Current selection: ', value['Name'])
    submit_button = st.form_submit_button(label='Discover the Land Surface Temperature Data!')

if submit_button:
    try:
        aoi_json = value['geometry']
    except TypeError:
        st.warning('Location is missing. Please select an urban area.')
        st.stop()
    st.success('The Land Surface Temperature will be collected for the following urban area: ' + value['Name'])
    aoi = ee.FeatureCollection(ee.Geometry(aoi_json)).geometry()
    # Getting LST data.
    lst = ee.ImageCollection('MODIS/061/MOD11A2').filterDate(date_range).select('LST_Day_1km')
    reduce_lst = gee.create_reduce_region_function(geometry=aoi, reducer=ee.Reducer.mean(), scale=1000, crs='EPSG:4326')
    lst_stat_fc = ee.FeatureCollection(lst.map(reduce_lst)).filter(ee.Filter.notNull(lst.first().bandNames()))
    lst_dict = gee.fc_to_dict(lst_stat_fc).getInfo()
    lst_df = pd.DataFrame(lst_dict)
    lst_df['LST_Day_1km'] = (lst_df['LST_Day_1km'] * 0.02 - 273.5)
    lst_df = gee.add_date_info(lst_df)

    # Creating Charts
    # Line Chart with Points: https://altair-viz.github.io/gallery/line_chart_with_points.html
    line_chart = alt.Chart(lst_df).mark_line(
        point=alt.OverlayMarkDef(color="red")
    ).encode(
        alt.X("Timestamp"),
        alt.Y("LST_Day_1km", title='Land Surface Temperature, °C'),
    ).interactive()

    # Ridgeline plot Example: https://altair-viz.github.io/gallery/ridgeline_plot.html
    step = 16
    overlap = 1

    ridgeline_plot = alt.Chart(lst_df, height=step).transform_timeunit(
        Month="month(Timestamp)"
    ).transform_joinaggregate(
        mean_temp="mean(LST_Day_1km)", groupby=['Month']
    ).transform_bin(
        ['bin_max', 'bin_min'], 'mean_temp'
    ).transform_aggregate(
        value='count()', groupby=['Month', 'mean_temp', 'bin_min', 'bin_max']
    ).transform_impute(
        impute='value', groupby=['Month', 'mean_temp'], key='bin_min', value=0
    ).mark_area(
        interpolate='monotone',
        fillOpacity=0.8,
        stroke='lightgray',
        strokeWidth=0.5
    ).encode(
        alt.X('bin_min:Q', bin='binned',
            title='Land Surface Temperature, °C'
        ),
        alt.Y(
            'value:Q',
            scale=alt.Scale(range=[step, -step * overlap]),
            axis=None
        ),
        alt.Fill(
            'mean_temp:Q',
            legend=None,
            scale=alt.Scale(domain=[40, -5], scheme='redyellowblue')
        )
    ).facet(
        row=alt.Row(
            "Month:T",
            title=None,
            header=alt.Header(labelAngle=0, labelAlign='right', format='%B')
        )
    ).properties(
        bounds='flush'
    ).configure_facet(
        spacing=0
    ).configure_view(
        stroke=None
    ).configure_title(
        anchor='end'
    )

    # Binned Heatmap: https://altair-viz.github.io/gallery/binned_heatmap.html
    binned_heatmap = alt.Chart(lst_df).mark_rect().encode(
        alt.X("Month:O"),
        alt.Y("Year:O"),
        alt.Color("mean(LST_Day_1km):Q", scale=alt.Scale(scheme='redyellowblue', reverse=True), title='Land Surface Temperature, °C')
    ).interactive()

    # Violin Plot Chart: https://altair-viz.github.io/gallery/violin_plot.html
    violin_chart = alt.Chart(lst_df).transform_density(
        "LST_Day_1km",
        as_=["LST_Day_1km", 'density'],
        extent=[-20, 60],
        groupby=["Year"]
    ).mark_area(orient='horizontal').encode(
        alt.Y("LST_Day_1km:Q",title='Land Surface Temperature, °C'),
        color="Year:N",
        x=alt.X(
            'density:Q',
            stack='center',
            impute=None,
            title=None,
            axis=alt.Axis(labels=False, values=[0],grid=False, ticks=True),
        ),
        column=alt.Column(
            "Year:Q",
            header=alt.Header(
                titleOrient='bottom',
                labelOrient='bottom',
                labelPadding=0,
            ),
        )
    ).properties(
        width=100,
        height=450
    ).configure_facet(
        spacing=0
    ).configure_view(
        stroke=None
    )

    # Hexbin Chart: https://altair-viz.github.io/gallery/hexbins.html
    # Size of the hexbins
    size = 15
    # Count of distinct x features
    xFeaturesCount = 12
    # Count of distinct y features
    yFeaturesCount = 6
    yField = 'Timestamp'
    xField = 'Timestamp'
    # the shape of a hexagon
    hexagon = "M0,-2.3094010768L2,-1.1547005384 2,1.1547005384 0,2.3094010768 -2,1.1547005384 -2,-1.1547005384Z"
    hexbin_chart = alt.Chart(lst_df).mark_point(size=size**2, shape=hexagon).encode(
        x=alt.X('xFeaturePos:Q', axis=alt.Axis(title='Month',
                                               grid=False, tickOpacity=0, domainOpacity=0)),
        y=alt.Y('year(' + yField + '):O', axis=alt.Axis(title='Year',
                                                       labelPadding=20, tickOpacity=0, domainOpacity=0)),
        stroke=alt.value('black'),
        strokeWidth=alt.value(0.2),
        fill=alt.Color('mean(LST_Day_1km):Q', scale=alt.Scale(scheme='redyellowblue', reverse=True), title='Land Surface Temperature, °C'),
        tooltip=['Month:O', 'Year:O', 'mean(LST_Day_1km):Q']
    ).transform_calculate(
        # This field is required for the hexagonal X-Offset
        xFeaturePos='(year(datum.' + yField + ') % 2) / 2 + month(datum.' + xField + ')'
    ).properties(
        # Scaling factors to make the hexbins fit. Adjusted to the streamlit view
        width=size * xFeaturesCount * 3.6,
        height=size * yFeaturesCount * 2.77128129216
    ).configure_view(
        strokeWidth=0
    ).interactive()

    # Boxplot Chart: https://altair-viz.github.io/gallery/boxplot.html
    boxplot_chart_year = alt.Chart(lst_df).mark_boxplot(extent='min-max').encode(
        alt.X('Year:O'),
        alt.Y('mean(LST_Day_1km):Q',title='Land Surface Temperature, °C')
    ).interactive()

    # Boxplot Chart: https://altair-viz.github.io/gallery/boxplot.html
    boxplot_chart_month = alt.Chart(lst_df).mark_boxplot(extent='min-max').encode(
        alt.X('Month:O'),
        alt.Y('mean(LST_Day_1km):Q', title='Land Surface Temperature, °C')
    ).properties(height=500).interactive()

    # Scatter Plot Chart: https://altair-viz.github.io/gallery/scatter_tooltips.html
    scatter_chart = alt.Chart(lst_df).mark_circle(size=60).encode(
        alt.Y('LST_Day_1km', title='Land Surface Temperature, °C'),
        alt.X('DOY', title='Day of the Year'),
        color='Year:N',
        tooltip=['LST_Day_1km', 'Timestamp']
    ).interactive()

    # Bar Chart with Negative Values: https://altair-viz.github.io/gallery/bar_chart_with_negatives.html
    bar_negative = alt.Chart(lst_df).mark_bar().encode(
        alt.X("Timestamp"),
        alt.Y("LST_Day_1km:Q", title='Land Surface Temperature, °C'),
        color=alt.condition(
            alt.datum.LST_Day_1km > 0,
            alt.value("orange"),  # The positive color
            alt.value("steelblue")  # The negative color
        )
    ).interactive()

    # Binned Scatterplot: https://altair-viz.github.io/gallery/binned_scatterplot.html
    scatter_binned = alt.Chart(lst_df).mark_circle().encode(
        alt.X('DOY:Q', bin=True, title='Day of the Year'),
        alt.Y('LST_Day_1km:Q', bin=True, title='Land Surface Temperature, °C'),
        size='count()'
    ).interactive()

    #Scatter Plot with LOESS Lines: https://altair-viz.github.io/gallery/scatter_with_loess.html
    base_scatter = alt.Chart(lst_df).mark_circle(opacity=0.5).encode(
        alt.X('DOY', title='Day of the Year'),
        alt.Y('LST_Day_1km:Q', title='Land Surface Temperature, °C'),
        alt.Color('Year:N')
    )
    scatter_loess = base_scatter + base_scatter.transform_loess('DOY', 'LST_Day_1km', groupby=['Year']).mark_line(size=4).interactive()

    # Stripplot: https://altair-viz.github.io/gallery/stripplot.html
    stripplot =  alt.Chart(lst_df, width=40).mark_circle(size=8).encode(
        x=alt.X(
            'jitter:Q',
            title=None,
            axis=alt.Axis(values=[0], ticks=True, grid=False, labels=False),
            scale=alt.Scale(),
        ),
        y=alt.Y('LST_Day_1km:Q', title='Land Surface Temperature, °C'),
        color=alt.Color('Year:N', legend=None),
        column=alt.Column(
            'Year:N',
            header=alt.Header(
                labelAngle=-90,
                titleOrient='top',
                labelOrient='bottom',
                labelAlign='right',
                labelPadding=3,
            ),
        ),
    ).transform_calculate(
        # Generate Gaussian jitter with a Box-Muller transform
        jitter='sqrt(-2*log(random()))*cos(2*PI*random())'
    ).configure_facet(
        spacing=0
    ).configure_view(
        stroke=None
    ).properties(height=400).interactive()

    # Table Bubble Plot: https://altair-viz.github.io/gallery/table_bubble_plot_github.html
    table_bubble = alt.Chart(lst_df).mark_circle().encode(
        alt.X('Month:O'),
        alt.Y('Year:O'),
        alt.Size('mean(LST_Day_1km):Q', title='Land Surface Temperature, °C')
    ).interactive()


    # Visualizing in the defined layout
    # Row 1
    col1, col2 = st.columns([4,1])
    with col1:
        st.altair_chart(line_chart, use_container_width=True)
    with col2:
        st.altair_chart(boxplot_chart_year, use_container_width=True)

    # Row 2
    col1, col2 = st.columns([1,1])
    with col1:
        st.altair_chart(binned_heatmap, use_container_width=True)
    with col2:
        st.altair_chart(table_bubble, use_container_width=True)

    # Row 3
    col1, col2 = st.columns([1,4])
    with col1:
        st.altair_chart(scatter_chart, use_container_width=True)
    with col2:
        st.altair_chart(bar_negative, use_container_width=True)

    # Row 4
    col1, col2, col3 = st.columns([1,2,1])
    with col1:
        st.altair_chart(boxplot_chart_month, use_container_width=True)
    with col2:
        st.altair_chart(violin_chart)
    with col3:
        st.altair_chart(stripplot)

    # Row 5
    col1, col2 = st.columns([1,1])
    with col1:
        st.altair_chart(hexbin_chart)
    with col2:
        st.altair_chart(ridgeline_plot)

    # Row 6
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        st.altair_chart(scatter_binned, use_container_width=True)
    with col2:
        st.altair_chart(scatter_chart, use_container_width=True)
    with col3:
        st.altair_chart(scatter_loess, use_container_width=True)

    col1, col2, col3 = st.columns([1, 4, 1])

    # Data download
    col1, col2, col3 = st.columns([1, 4, 1]) 
    col2.markdown("""
        ---
        ## Data download
        """)
    # Download data preparation
    gdf = gpd.GeoDataFrame(lst_df, geometry=[shape(aoi_json)]*len(lst_df))
    csv_data = convert_df(gdf)
    geojson_data = convert_gdf(gdf)
    col2.warning('Please note, data download resets the dashboard view. This seems to be a Streamlit limitation as described in [this open issue](https://github.com/streamlit/streamlit/issues/4382).')
    # Download CSV
    with col2.container(border=True):
        cont1_1, cont1_2 = st.columns([1, 3])
        with cont1_1:
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name=value['Name'] + "-LST.csv",
                mime="text/csv",
                key='download-csv'
            )
        with cont1_2:
            st.write('The CSV file includes the average land surface temperature value in Celsius, date and time information and the hydrological basin geometry in the WKT format.')
    # Download GeoJSON
    with col2.container(border=True):
        cont2_1, cont2_2 = st.columns([1, 3])
        with cont2_1:
            st.download_button(
                label="Download GeoJSON",
                data=geojson_data,
                file_name=value['Name'] + "-LST.geojson",
                mime="application/json",
                key='download-geojson'
            )
        with cont2_2:
            st.write('The GeoJSON provides the same geometry values for each feature. GeoJSON properties include the average land surface temperature value, date and time infromation.')

    col1, col2, col3 = st.columns([1, 4, 1])
    col2.markdown("""
        ---
        ## References
        * World Urban Areas - [ArcGIS Hub](https://hub.arcgis.com/datasets/schools-BE::world-urban-areas/explore).
        * Land Surface Temperature - [MODIS via Google Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A2).
        * Map rendering - [PyDeck](https://deckgl.readthedocs.io/en/latest/) within [streamlit-deckgl](https://pypi.org/project/streamlit-deckgl/0.5.1/).
        * Library for visualizations - [Vega-Altair](https://altair-viz.github.io/index.html).

        """)
    col2.info('''Please help locating the original vector data source.''')

