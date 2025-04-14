import streamlit as st
import importlib
from grpc_status import rpc_status

# Import page functions
from pages.geocoding import geocoding_page
from pages.boundary import display_boundary_page
from pages.kml_converter import convert_kml_to_geojson
from pages.query_apis import query_apis_page
from pages.search_pois import search_pois
from pages.get_map_pois import fetch_pois_page
from pages.get_simpleview_pois import get_simpleview_pois_page
from pages.scrape_poi_images import scrape_poi_images_page
from pages.get_categories import get_categories_page
from pages.get_wander_tags import get_wander_tags_page
from pages.assign_tags_to_pois import assign_tags_to_pois_page
from pages.compare_changes import compare_pois_page
from pages.add_wander_ids import match_wander_ids_page
from pages.analyze_video import video_analysis_page
from pages.query_video_data import query_video_data_page
from pages.raleigh_step_1 import raleigh_page_1
from pages.raleigh_step_2 import raleigh_page_2
from pages.raleigh_step_3 import raleigh_page_3
from pages.raleigh_step_4 import raleigh_page_4
from pages.assign_category_to_pois import assign_categories_to_pois_page
from pages.test_social_saving import test_social_saving_page
from pages.get_wildapricot_pois import get_wildapricot_contacts_page

import pages.query_apis as query_apis
import pages.boundary as boundary
import pages.geocoding as geocoding
import pages.kml_converter as kml_converter
import pages.search_pois as search_poi_page
import pages.get_map_pois as get_map_pois
import pages.get_simpleview_pois as get_simpleview_pois
import pages.scrape_poi_images as scrape_poi_images
import pages.get_categories as get_categories
import pages.get_wander_tags as get_tags
import pages.assign_tags_to_pois as assign_tags
import pages.compare_changes as compare_changes
import pages.add_wander_ids as add_wander_ids
import pages.analyze_video as analyze_video
import pages.query_video_data as query_video_data
import pages.raleigh_step_1 as raleigh_step_1
import pages.raleigh_step_2 as raleigh_step_2
import pages.raleigh_step_3 as raleigh_step_3
import pages.raleigh_step_4 as raleigh_step_4
import pages.assign_category_to_pois as assign_categories_to_pois
import pages.test_social_saving as test_social_saving
import pages.get_wildapricot_pois as get_wild_apricot_pois


# TODO
# make these enums
# changes aga

# Ensure changes are reloaded
def reload_modules():
    importlib.reload(query_apis)
    importlib.reload(boundary)
    importlib.reload(geocoding)
    importlib.reload(kml_converter)
    importlib.reload(search_poi_page)
    importlib.reload(get_map_pois)
    importlib.reload(get_simpleview_pois)
    importlib.reload(scrape_poi_images)
    importlib.reload(get_categories)
    importlib.reload(get_tags)
    importlib.reload(assign_tags)
    importlib.reload(compare_changes)
    importlib.reload(add_wander_ids)
    importlib.reload(analyze_video)
    importlib.reload(query_video_data)
    importlib.reload(raleigh_step_1)
    importlib.reload(raleigh_step_2)
    importlib.reload(raleigh_step_3)
    importlib.reload(raleigh_step_4)
    importlib.reload(assign_categories_to_pois)
    importlib.reload(test_social_saving)
    importlib.reload(get_wild_apricot_pois)


# Call reload before using the module
reload_modules()


# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to", ["Geocoding", "Get Boundary", "Convert KML", "Search POIs", "Query APIs", "Get Map POIs", "Get Simpleview POIs", "Scrape POI Images", "Get Categories", "Get Wander Tags", "Assign Tags to POIs", "Assign Categories to POIs", "Compare Changes", "Match Wander Ids", "Analyze Video", "Query Video Data", "Raleigh 1", "Raleigh 2", "Raleigh 3", "Raleigh 4", "Social Saving Test", "Get Upcountry POIs"])

# Display selected page
if page == "Geocoding":
    geocoding_page()
elif page == "Get Boundary":
    display_boundary_page()
elif page == "Convert KML":
    convert_kml_to_geojson()
elif page == "Search POIs":
    search_pois()
elif page == "Query APIs":
    query_apis_page()
elif page == "Get Map POIs":
    fetch_pois_page()
elif page == "Get Simpleview POIs":
    get_simpleview_pois_page()
elif page == "Scrape POI Images":
    scrape_poi_images_page()
elif page == "Get Categories":
    get_categories_page()
elif page == "Get Wander Tags":
    get_wander_tags_page()
elif page == "Assign Tags to POIs":
    assign_tags_to_pois_page()
elif page == "Compare Changes":
    compare_pois_page()
elif page == "Match Wander Ids":
    match_wander_ids_page()
elif page == "Analyze Video":
    video_analysis_page()
elif page == "Query Video Data":
    query_video_data_page()
elif page == "Raleigh 1":
    raleigh_page_1()
elif page == "Raleigh 2":
    raleigh_page_2()
elif page == "Raleigh 3":
    raleigh_page_3()
elif page == "Raleigh 4":
    raleigh_page_4()
elif page == "Assign Categories to POIs":
    assign_categories_to_pois_page()
elif page == "Social Saving Test":
    test_social_saving_page()
elif page == "Get Upcountry POIs":
    get_wildapricot_contacts_page()
