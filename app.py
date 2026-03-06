import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from datetime import datetime
from geopy.geocoders import Nominatim

# 1. PAGE CONFIGURATION
st.set_page_config(layout="wide", page_title="NYC Taxi Fare Predictor", page_icon="🚕")

# 2. INITIALIZATION
if 'fare_calculated' not in st.session_state: st.session_state.fare_calculated = False
if 'ordered' not in st.session_state: st.session_state.ordered = False
if 'p_addr' not in st.session_state: st.session_state.p_addr = ""
if 'd_addr' not in st.session_state: st.session_state.d_addr = ""

# 3. PRETTIER UI (Custom CSS)
button_color = "#28a745" if st.session_state.ordered else "#FF4B4B"

st.markdown(f"""
    <style>
    /* Main Background */
    .stApp {{
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }}

    /* Card Styling */
    div[data-testid="stVerticalBlock"] > div:has(div.stMetric) {{
        background: rgba(255, 255, 255, 0.8);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }}

    /* Button Styling */
    div.stButton > button {{
        border-radius: 8px !important;
        height: 3em !important;
        transition: all 0.3s ease !important;
    }}

    /* The Order Now Button Dynamic Color */
    div.stButton > button[kind="primary"]:first-of-type {{
        background-color: {button_color} !important;
        border: none !important;
        box-shadow: 0 4px 12px {button_color}66;
    }}

    /* Title Styling */
    h1 {{
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 800;
        color: #1e293b;
        letter-spacing: -1px;
    }}
    </style>
    """, unsafe_allow_html=True)

# 4. UTILITIES
url = st.secrets["url_base"]
geolocator = Nominatim(user_agent="nyc_taxi_pro_v4")

def search_location(query):
    """Finds the best NYC match and returns (Display Name, Lon, Lat)"""
    if not query or len(query) < 3: return None
    try:
        # We force 'New York City' into the query for better accuracy
        location = geolocator.geocode(f"{query}, NYC", timeout=10, addressdetails=True)
        if location:
            # Shorten the name (e.g., "Empire State Building, 5th Ave...")
            short_name = location.address.split(',')[0] + ", " + location.address.split(',')[1]
            return {"name": short_name, "lon": location.longitude, "lat": location.latitude}
    except: pass
    return None

# --- 5. LAYOUT ---
st.title("🚕 NYC Fare Predictor")
st.caption("Enter a landmark (e.g., 'Grand Central' or 'MOMA') to find your ride.")

left_col, right_col = st.columns([1, 1.5], gap="large")

with left_col:
    with st.container():
        st.subheader("📍 Trip Details")

        # SEARCH LOGIC: Pickup
        raw_pickup = st.text_input("PICKUP", placeholder="e.g. Empire State Building")
        p_res = search_location(raw_pickup)
        if p_res:
            st.success(f"📍 Found: **{p_res['name']}**")
            p_lon, p_lat = p_res['lon'], p_res['lat']

        # SEARCH LOGIC: Destination
        raw_dropoff = st.text_input("DESTINATION", placeholder="e.g. JFK Airport")
        d_res = search_location(raw_dropoff)
        if d_res:
            st.info(f"🏁 Found: **{d_res['name']}**")
            d_lon, d_lat = d_res['lon'], d_res['lat']

        passengers = st.pills("PASSENGERS", options=[1, 2, 3, 4, 5, "6+"], default=1)

    st.write("---")

    # Date/Time Logic
    now_dt = datetime.now()
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
        if st.button("ORDER NOW 🚕", use_container_width=True, type="primary"):
            st.session_state.ordered = True
            st.session_state.date, st.session_state.time = now_dt.date(), now_dt.time()
            st.rerun()

    with c2:
        scheduled_dt = st.datetime_input("SCHEDULE LATER", value=now_dt)
        s_date, s_time = scheduled_dt.date(), scheduled_dt.time()

    if st.session_state.ordered:
        s_date, s_time = st.session_state.get('date', s_date), st.session_state.get('time', s_time)

    st.write("##")
    btn_area = st.empty()
    eval_click = False
    if not st.session_state.fare_calculated:
        eval_click = btn_area.button("EVALUATE MY FARE", use_container_width=True)

# --- 6. MAP & PREDICTION ---
if raw_pickup and raw_dropoff and p_res and d_res:
    # Get Route
    osrm = f"http://router.project-osrm.org/route/v1/driving/{p_lon},{p_lat};{d_lon},{d_lat}?overview=full&geometries=geojson"
    route_data = requests.get(osrm).json()
    path = route_data['routes'][0]['geometry']['coordinates']
    dist = route_data['routes'][0]['distance'] / 1000

    with right_col:
        st.metric("Estimated Distance", f"{dist:.2f} km")
        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/navigation-day-v1",
            initial_view_state=pdk.ViewState(latitude=(p_lat+d_lat)/2, longitude=(p_lon+d_lon)/2, zoom=12),
            layers=[
                pdk.Layer("PathLayer", [{"path": path}], get_path="path", get_color=[40, 167, 69], width_min_pixels=4),
                pdk.Layer("ScatterplotLayer", [{"pos": [p_lon, p_lat]}, {"pos": [d_lon, d_lat]}],
                          get_position="pos", get_color=[255, 75, 75], get_radius=150)
            ]
        ))

    # Prediction
    if eval_click:
        p_datetime = f"{s_date} {s_time.strftime('%H:%M:%S')}"
        p_count = 6 if passengers == "6+" else passengers
        params = {
            "pickup_datetime": p_datetime, "pickup_longitude": p_lon, "pickup_latitude": p_lat,
            "dropoff_longitude": d_lon, "dropoff_latitude": d_lat, "passenger_count": p_count
        }
        try:
            res = requests.get(url, params=params, timeout=10).json()
            st.session_state.current_fare = res.get("fare", 0.0)
            st.session_state.fare_calculated = True
            st.rerun()
        except: st.error("Prediction service unreachable.")

if st.session_state.fare_calculated:
    with left_col:
        btn_area.success(f"### 💰 Est. Fare: ${st.session_state.current_fare:.2f}")
        if st.button("Clear / New Trip"):
            st.session_state.fare_calculated = False
            st.session_state.ordered = False
            st.rerun()
