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
if 'current_fare' not in st.session_state: st.session_state.current_fare = 0.0

# Dynamic Green/Red Button CSS
button_color = "#28a745" if st.session_state.ordered else "#FF4B4B"
st.markdown(f"""
    <style>
    html, body, [class*="View"] {{ font-size: 18px !important; }}
    div.stButton > button[kind="primary"]:first-child {{
        background-color: {button_color} !important;
        color: white !important;
        border: none !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
# Cache the geocoder to speed up repeated lookups
@st.cache_data(show_spinner=False)
def get_coords(address):
    if not address: return None, None
    try:
        # Using a very specific user_agent prevents 403 Forbidden/Slow errors
        geolocator = Nominatim(user_agent="taxi_app_user_unique_12345")
        location = geolocator.geocode(f"{address}, NYC", timeout=3)
        return (location.longitude, location.latitude) if location else (None, None)
    except: return None, None

def get_route(start_lon, start_lat, end_lon, end_lat):
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=2).json()
        if r.get('routes'):
            return r['routes'][0]['geometry']['coordinates'], r['routes'][0]['distance'] / 1000
    except: pass
    return [[start_lon, start_lat], [end_lon, end_lat]], 0.0

# --- 4. LAYOUT ---
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
        if st.button("ORDER NOW 🚕", type="primary", use_container_width=True):
            st.session_state.ordered = True
            st.session_state.date, st.session_state.time = now_dt.date(), now_dt.time()
            st.rerun()

    with c2:
        scheduled_dt = st.datetime_input("SCHEDULE LATER", value=now_dt)
        sel_date, sel_time = scheduled_dt.date(), scheduled_dt.time()

    if st.session_state.ordered:
        sel_date, sel_time = st.session_state.get('date', sel_date), st.session_state.get('time', sel_time)

    st.write("##")
    btn_placeholder = st.empty()
    eval_click = False
    if not st.session_state.fare_calculated:
        eval_click = btn_placeholder.button("EVALUATE MY FARE", use_container_width=True)

# --- 5. MAP & PREDICTION LOGIC ---
if pickup and dropoff:
    p_lon, p_lat = get_coords(pickup)
    d_lon, d_lat = get_coords(dropoff)

    if p_lon and d_lon:
        road_path, total_dist = get_route(p_lon, p_lat, d_lon, d_lat)

        with right_col:
            st.metric("Estimated Travel Distance", f"{total_dist:.2f} km")
            st.pydeck_chart(pdk.Deck(
                map_style="mapbox://styles/mapbox/light-v9",
                initial_view_state=pdk.ViewState(latitude=(p_lat+d_lat)/2, longitude=(p_lon+d_lon)/2, zoom=12),
                layers=[
                    pdk.Layer("PathLayer", [{"path": road_path}], get_path="path", get_color=[255, 75, 75], width_min_pixels=5),
                    pdk.Layer("ScatterplotLayer", [{"pos":[p_lon, p_lat]}, {"pos":[d_lon, d_lat]}], get_position="pos", get_color=[255, 75, 75], get_radius=200)
                ]
            ))

        if eval_click:
            # PREDICTION CALL
            url_base = st.secrets["url_base"]
            pickup_datetime = f"{sel_date} {sel_time.strftime('%H:%M:%S')}"

            params = {
                "pickup_datetime": pickup_datetime,
                "pickup_longitude": p_lon, "pickup_latitude": p_lat,
                "dropoff_longitude": d_lon, "dropoff_latitude": d_lat,
                "passenger_count": int(passengers)
            }

            try:
                # DEBUG: Remove this line once it works
                # st.write(f"Testing URL: {url_base}")

                response = requests.get(url_base, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # We use .get("fare") but check for "prediction" as some APIs use different keys
                    st.session_state.current_fare = data.get("fare") or data.get("prediction") or 0.0
                    st.session_state.fare_calculated = True
                    st.rerun()
                else:
                    st.error(f"API Error {response.status_code}: {response.text}")
            except Exception as e:
                st.error(f"Connection Failed: {e}")
    else:
        right_col.warning("Still looking for those addresses... try adding 'NY' if it takes too long.")

if st.session_state.fare_calculated:
    btn_placeholder.success(f"### 💰 Estimated Fare: ${st.session_state.current_fare:.2f}")
    if st.button("Calculate New Trip"):
        st.session_state.fare_calculated = False
        st.session_state.ordered = False
        st.rerun()
