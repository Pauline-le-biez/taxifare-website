import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from datetime import datetime
from geopy.geocoders import Nominatim

# 1. PAGE CONFIGURATION
st.set_page_config(layout="wide", page_title="Taxi Fare Predictor")

# 2. INITIALIZATION & STYLING
if 'fare_calculated' not in st.session_state:
    st.session_state.fare_calculated = False
if 'ordered' not in st.session_state:
    st.session_state.ordered = False

# Inject CSS for the Green Button and UI
st.markdown(f"""
    <style>
    html, body, [class*="View"] {{ font-size: 18px !important; }}
    .stButton button p {{ font-size: 22px !important; font-weight: bold !important; }}
    /* Change button color to green if 'ordered' is True */
    div.stButton > button:first-child {{
        background-color: {"#28a745" if st.session_state.ordered else "#FF4B4B"} !important;
        color: white !important;
    }}
    </style>
    """, unsafe_allow_html=True)

url = st.secrets["url_base"]
# Added a more specific user_agent to avoid Nominatim blocks
geolocator = Nominatim(user_agent="nyc_taxi_predictor_app_v2")

def get_coords(address):
    if not address: return None, None
    try:
        # Adding 'New York' to the string helps Nominatim find NYC locations faster
        location = geolocator.geocode(f"{address}, New York", timeout=10)
        if location:
            return location.longitude, location.latitude
    except:
        pass
    return None, None

def get_route(start_lon, start_lat, end_lon, end_lat):
    osrm_url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
    try:
        response = requests.get(osrm_url).json()
        if response.get('routes'):
            route = response['routes'][0]
            return route['geometry']['coordinates'], route['distance'] / 1000
    except:
        pass
    return [[start_lon, start_lat], [end_lon, end_lat]], 0.0

# --- 3. LAYOUT ---
st.title("🚕 HOW MUCH COSTS MY FUTURE RIDE?")
left_col, right_col = st.columns([1, 1.5], gap="large")

with left_col:
    pickup = st.text_input("PICKUP LOCATION", placeholder="e.g. Empire State Building")
    dropoff = st.text_input("DESTINATION", placeholder="e.g. Central Park")
    passengers = st.pills("PASSENGERS", options=list(range(1, 9)), default=1)

    st.write("---")
    now_dt = datetime.now()
    c1, c2 = st.columns([1, 2])

    with c1:
        st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
        # The "ORDER NOW" Button
        if st.button("ORDER NOW 🚕", use_container_width=True):
            st.session_state.ordered = True
            st.session_state.date = now_dt.date()
            st.session_state.time = now_dt.time()
            st.rerun()

    with c2:
        scheduled_dt = st.datetime_input("SCHEDULE LATER", value=now_dt)
        selected_date = scheduled_dt.date()
        selected_time = scheduled_dt.time()

    # Apply Session State overrides if "Order Now" was clicked
    if st.session_state.ordered:
        selected_date = st.session_state.get('date', selected_date)
        selected_time = st.session_state.get('time', selected_time)

    st.write("##")
    button_placeholder = st.empty()

    # "EVALUATE" button logic
    evaluate_clicked = False
    if not st.session_state.fare_calculated:
        evaluate_clicked = button_placeholder.button("EVALUATE MY FARE", use_container_width=True, type="primary")

# --- 4. DATA PROCESSING & MAP (Right Column) ---
p_lon, p_lat, d_lon, d_lat = None, None, None, None

if pickup and dropoff:
    with st.spinner("Locating addresses..."):
        p_lon, p_lat = get_coords(pickup)
        d_lon, d_lat = get_coords(dropoff)

    if p_lon and d_lon:
        road_path, total_dist = get_route(p_lon, p_lat, d_lon, d_lat)

        with right_col:
            st.metric("Estimated Travel Distance", f"{total_dist:.2f} km")
            st.pydeck_chart(pdk.Deck(
                map_style="mapbox://styles/mapbox/light-v9",
                initial_view_state=pdk.ViewState(
                    latitude=(p_lat + d_lat) / 2,
                    longitude=(p_lon + d_lon) / 2,
                    zoom=12,
                ),
                layers=[
                    pdk.Layer("PathLayer", [{"path": road_path}], get_path="path", get_color=[255, 75, 75], width_min_pixels=5),
                    pdk.Layer("ScatterplotLayer", [
                        {"pos": [p_lon, p_lat], "color": [255, 75, 75]},
                        {"pos": [d_lon, d_lat], "color": [156, 204, 101]}
                    ], get_position="pos", get_color="color", get_radius=150, radius_min_pixels=8)
                ]
            ))
    else:
        right_col.error("Could not find one of the addresses. Please be more specific (e.g., add 'NY').")
else:
    right_col.info("👋 Enter your pickup and destination on the left to start.")

# --- 5. PREDICTION LOGIC ---
if evaluate_clicked:
    if not (p_lon and d_lon):
        st.error("Please enter valid locations first!")
    else:
        pickup_datetime = f"{selected_date} {selected_time.strftime('%H:%M:%S')}"
        params = {
            "pickup_datetime": pickup_datetime,
            "pickup_longitude": p_lon, "pickup_latitude": p_lat,
            "dropoff_longitude": d_lon, "dropoff_latitude": d_lat,
            "passenger_count": passengers
        }

        with st.spinner("Connecting to API..."):
            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.current_fare = data.get("fare", 0.0)
                    st.session_state.fare_calculated = True
                    st.rerun()
                else:
                    st.error(f"API Error: Status {response.status_code}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

# Display Result
if st.session_state.fare_calculated:
    button_placeholder.success(f"### 💰 Estimated Fare: ${st.session_state.current_fare:.2f}")
    if st.button("Calculate New Trip"):
        st.session_state.fare_calculated = False
        st.session_state.ordered = False
        st.rerun()
