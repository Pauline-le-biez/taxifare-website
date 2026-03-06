import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from datetime import datetime
from geopy.geocoders import Nominatim

# 1. PAGE CONFIGURATION
st.set_page_config(layout="wide", page_title="Taxi Fare Predictor")

# 2. INITIALIZATION & STATE
if 'fare_calculated' not in st.session_state: st.session_state.fare_calculated = False
if 'ordered' not in st.session_state: st.session_state.ordered = False

# CSS for the Red/Green Button and UI
button_color = "#28a745" if st.session_state.ordered else "#FF4B4B"
st.markdown(f"""
    <style>
    html, body, [class*="View"] {{ font-size: 18px !important; }}
    /* Targets the 'Order Now' button specifically */
    div.stButton > button[kind="primary"]:first-child {{
        background-color: {button_color} !important;
        color: white !important;
        border: none !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# 3. FAST UTILITIES
# Cache coordinates so the app doesn't freeze on every click
@st.cache_data(show_spinner=False)
def get_coords(address):
    if not address or len(address) < 3: return None, None
    try:
        # We add 'New York City' to force the geocoder to stay in the right area
        geolocator = Nominatim(user_agent="taxi_fare_predictor_final")
        location = geolocator.geocode(f"{address}, New York City", timeout=5)
        return (location.longitude, location.latitude) if location else (None, None)
    except: return None, None

def get_route(p_lon, p_lat, d_lon, d_lat):
    url = f"http://router.project-osrm.org/route/v1/driving/{p_lon},{p_lat};{d_lon},{d_lat}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=3).json()
        if r.get('routes'):
            return r['routes'][0]['geometry']['coordinates'], r['routes'][0]['distance'] / 1000
    except: pass
    return [[p_lon, p_lat], [d_lon, d_lat]], 0.0

# --- 4. LAYOUT ---
st.title("🚕 HOW MUCH COSTS MY FUTURE RIDE?")

left_col, right_col = st.columns([1, 1.5], gap="large")

with left_col:
    pickup = st.text_input("PICKUP LOCATION", placeholder="e.g. Empire State Building", value="Grand Central, NY")
    dropoff = st.text_input("DESTINATION", placeholder="e.g. MOMA", value="MOMA, NY")
    passengers = st.pills("PASSENGERS", options=list(range(1, 9)), default=1)

    st.write("---")
    now_dt = datetime.now()
    c1, c2 = st.columns([1, 2])

    with c1:
        st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
        if st.button("ORDER NOW 🚕", type="primary", use_container_width=True):
            st.session_state.ordered = True
            st.session_state.date, st.session_state.time = now_dt.date(), now_dt.time()
            st.rerun()

    with c2:
        scheduled_dt = st.datetime_input("SCHEDULE LATER", value=now_dt)
        sel_date, sel_time = scheduled_dt.date(), scheduled_dt.time()

    # Use "Order Now" time if clicked
    if st.session_state.ordered:
        sel_date = st.session_state.get('date', sel_date)
        sel_time = st.session_state.get('time', sel_time)

    st.write("##")
    btn_area = st.empty()
    eval_clicked = False
    if not st.session_state.fare_calculated:
        eval_clicked = btn_area.button("EVALUATE MY FARE", use_container_width=True)

# --- 5. THE LOGIC ENGINE ---
p_lon, p_lat = get_coords(pickup)
d_lon, d_lat = get_coords(dropoff)

if p_lon and d_lon:
    road_path, total_dist = get_route(p_lon, p_lat, d_lon, d_lat)

    with right_col:
        st.metric("Estimated Travel Distance", f"{total_dist:.2f} km")
        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state=pdk.ViewState(latitude=(p_lat+d_lat)/2, longitude=(p_lon+d_lon)/2, zoom=13),
            layers=[
                pdk.Layer("PathLayer", [{"path": road_path}], get_path="path", get_color=[255, 75, 75], width_min_pixels=5),
                pdk.Layer("ScatterplotLayer", [{"pos":[p_lon, p_lat]}, {"pos":[d_lon, d_lat]}], get_position="pos", get_color=[255, 75, 75], get_radius=150)
            ]
        ))

    if eval_clicked:
        # PREDICTION API CALL
        api_url = f"{st.secrets['url_base'].rstrip('/')}/predict"
        # Format date exactly as your FastAPI expects: %Y-%m-%d %H:%M:%S
        pickup_dt_str = f"{sel_date} {sel_time.strftime('%H:%M:%S')}"

        params = {
            "pickup_datetime": pickup_dt_str,
            "pickup_longitude": float(p_lon),
            "pickup_latitude": float(p_lat),
            "dropoff_longitude": float(d_lon),
            "dropoff_latitude": float(d_lat),
            "passenger_count": int(passengers)
        }

        with st.spinner("Calculating fare..."):
            try:
                response = requests.get(api_url, params=params, timeout=
