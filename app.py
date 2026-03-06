import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from datetime import datetime, timedelta, time
from geopy.geocoders import Nominatim

# 1. PAGE CONFIGURATION
st.set_page_config(layout="wide", page_title="Taxi Fare Predictor")

# 2. ENHANCED STYLING
st.markdown("""
    <style>
    /* Global Typography */
    html, body, [class*="View"] { font-size: 18px !important; }
    .stButton button p { font-size: 22px !important; font-weight: bold !important; }
    .stTextInput label, .stDateInput label, .stSelectbox label { font-size: 20px !important; font-weight: bold !important; }

    /* Header Styles */
    h1 { font-size: 45px !important; color: #1E1E1E; padding-bottom: 20px; }

    /* Metric and Result Styling */
    [data-testid="stMetricValue"] { font-size: 40px !important; color: #FF4B4B; }

    /* Remove vertical spacing between widgets */
    .block-container { padding-top: 3rem; }
    </style>
    """, unsafe_allow_html=True)

# 3. INITIALIZATION & UTILITIES
if 'fare_calculated' not in st.session_state:
    st.session_state.fare_calculated = False

url = st.secrets["url_base"]
geolocator = Nominatim(user_agent="taxifare_app_final")

def get_coords(address):
    if not address: return None, None
    try:
        location = geolocator.geocode(address, timeout=10)
        return (location.longitude, location.latitude) if location else (None, None)
    except: return None, None

def get_route(start_lon, start_lat, end_lon, end_lat):
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
    try:
        response = requests.get(url).json()
        if response.get('routes'):
            route = response['routes'][0]
            return route['geometry']['coordinates'], route['distance'] / 1000
    except: pass
    return [[start_lon, start_lat], [end_lon, end_lat]], 0.0

# --- 4. DASHBOARD LAYOUT ---
st.title("🚕 HOW MUCH COST MY FUTURE RIDE?")

left_col, right_col = st.columns([1, 1.5], gap="large")

with left_col:
    # 1. Location Inputs First
    pickup = st.text_input("PICKUP LOCATION", placeholder="e.g. 75 rue de Rome Paris")
    dropoff = st.text_input("DESTINATION", placeholder="e.g. 73 rue Nollet Paris")
    passengers = st.pills("PASSENGERS", options=list(range(1, 9)), default=1)

    # 2. Date/Time Setup (Now below Passengers)
    st.write("---")
    now_dt = datetime.now()
    c1, c2 = st.columns([1, 2])

    with c1:
        st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
        if st.button("ORDER NOW 🚕", type="primary", use_container_width=True):
            st.session_state.date = now_dt.date()
            st.session_state.time = now_dt.time()
            st.session_state.fare_calculated = False # Reset on new order

    with c2:
        scheduled_dt = st.datetime_input("SCHEDULE LATER", value=now_dt, format="DD/MM/YYYY")
        selected_date = scheduled_dt.date()
        selected_time = scheduled_dt.time()

    # Apply Session State overrides
    if 'date' in st.session_state:
        selected_date, selected_time = st.session_state.date, st.session_state.time

    st.write("##") # Spacer

    # 3. DYNAMIC BUTTON / RESULT AREA
    button_placeholder = st.empty()

    # Logic to trigger evaluation
    evaluate_clicked = False
    if not st.session_state.fare_calculated:
        evaluate_clicked = button_placeholder.button("EVALUATE MY FARE", use_container_width=True, type="primary")

with right_col:
    if pickup and dropoff:
        p_lon, p_lat = get_coords(pickup)
        d_lon, d_lat = get_coords(dropoff)

        if p_lon and d_lon:
            road_path, total_dist = get_route(p_lon, p_lat, d_lon, d_lat)

            # Distance Metric
            st.metric("Estimated Travel Distance", f"{total_dist:.2f} km")

            # Map with focused view state
            st.pydeck_chart(pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                initial_view_state=pdk.ViewState(
                    latitude=(p_lat + d_lat) / 2,
                    longitude=(p_lon + d_lon) / 2,
                    zoom=14 if total_dist < 3 else 11 if total_dist < 20 else 6,
                    pitch=0
                ),
                layers=[
                    pdk.Layer("PathLayer", [{"path": road_path}], get_path="path", get_color=[255, 75, 75], width_min_pixels=5),
                    pdk.Layer("ScatterplotLayer", [
                        {"pos": [p_lon, p_lat], "color": [255, 75, 75]},
                        {"pos": [d_lon, d_lat], "color": [156, 204, 101]}
                    ], get_position="pos", get_color="color", get_radius=100, radius_min_pixels=8)
                ]
            ))

            # --- API CALCULATION LOGIC ---
            if evaluate_clicked:
                pickup_datetime = f"{selected_date} {selected_time.strftime('%H:%M:%S')}"
                params = {
                    "pickup_datetime": pickup_datetime, "pickup_longitude": p_lon, "pickup_latitude": p_lat,
                    "dropoff_longitude": d_lon, "dropoff_latitude": d_lat, "passenger_count": passengers
                }

                with st.spinner("Calculating fare..."):
                    try:
                        response = requests.get(url, params=params)
                        data = response.json()
                        st.session_state.current_fare = data.get("fare", 0.0)
                        st.session_state.fare_calculated = True
                        st.rerun() # Refresh to swap button for success banner
                    except:
                        st.error("Could not connect to the Prediction API.")

    else:
        st.info("👋 Enter your pickup and destination on the left to start.")

# --- 5. THE SWAP: Display Fare in Left Column if calculated ---
if st.session_state.fare_calculated:
    with left_col:
        # Re-using the placeholder to replace the button
        button_placeholder.success(f"### 💰 Estimated Fare: {st.session_state.current_fare:.2f} $")
        if st.button("Calculate New Trip", use_container_width=True):
            st.session_state.fare_calculated = False
            st.rerun()
