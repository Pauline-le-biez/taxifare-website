import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from datetime import datetime

# 1. CONFIGURATION & STATE
st.set_page_config(layout="wide", page_title="Taxi Fare Predictor")

if 'fare_calculated' not in st.session_state: st.session_state.fare_calculated = False
if 'ordered' not in st.session_state: st.session_state.ordered = False
if 'current_fare' not in st.session_state: st.session_state.current_fare = 0.0

# 2. BASE DE DONNÉES DES MONUMENTS (Évite le géocodage lent)
NYC_LANDMARKS = {
    "Empire State Building": {"lat": 40.7484, "lon": -73.9857},
    "Central Park (Strawberry Fields)": {"lat": 40.7750, "lon": -73.9750},
    "JFK Airport": {"lat": 40.6413, "lon": -73.7781},
    "Grand Central Terminal": {"lat": 40.7527, "lon": -73.9772},
    "Times Square": {"lat": 40.7580, "lon": -73.9855},
    "Statue of Liberty (Battery Park)": {"lat": 40.7033, "lon": -74.0170},
    "Brooklyn Bridge": {"lat": 40.7061, "lon": -73.9969},
    "MOMA": {"lat": 40.7614, "lon": -73.9776},
    "Wall Street": {"lat": 40.7060, "lon": -74.0088}
}

# 3. STYLE DYNAMIQUE (Bouton Rouge -> Vert)
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

# --- 4. LAYOUT ---
st.title("🚕 HOW MUCH COSTS MY FUTURE RIDE?")
left_col, right_col = st.columns([1, 1.5], gap="large")

with left_col:
    # Menu déroulant pour une sélection sans erreur
    pickup_name = st.selectbox("PICKUP LOCATION", options=list(NYC_LANDMARKS.keys()))
    dropoff_name = st.selectbox("DESTINATION", options=list(NYC_LANDMARKS.keys()), index=1)

    # Extraction immédiate des coordonnées
    p_coords = NYC_LANDMARKS[pickup_name]
    d_coords = NYC_LANDMARKS[dropoff_name]

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

    # Application du temps "Order Now" si activé
    if st.session_state.ordered:
        sel_date = st.session_state.get('date', sel_date)
        sel_time = st.session_state.get('time', sel_time)

    st.write("##")
    btn_area = st.empty()
    eval_click = False
    if not st.session_state.fare_calculated:
        eval_click = btn_area.button("EVALUATE MY FARE", use_container_width=True)

# --- 5. CARTE & CALCUL DE DISTANCE ---
with right_col:
    # Calcul d'itinéraire réel via OSRM
    osrm_url = f"http://router.project-osrm.org/route/v1/driving/{p_coords['lon']},{p_coords['lat']};{d_coords['lon']},{d_coords['lat']}?overview=full&geometries=geojson"
    try:
        response = requests.get(osrm_url, timeout=5).json()
        route_path = response['routes'][0]['geometry']['coordinates']
        total_dist_km = response['routes'][0]['distance'] / 1000
    except:
        route_path = [[p_coords['lon'], p_coords['lat']], [d_coords['lon'], d_coords['lat']]]
        total_dist_km = 0.0

    # Affichage des KM réalisés
    st.metric("Distance du trajet", f"{total_dist_km:.2f} KM")

    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v9",
        initial_view_state=pdk.ViewState(
            latitude=(p_coords['lat']+d_coords['lat'])/2,
            longitude=(p_coords['lon']+d_coords['lon'])/2,
            zoom=12
        ),
        layers=[
            pdk.Layer("PathLayer", [{"path": route_path}], get_path="path", get_color=[255, 75, 75], width_min_pixels=5),
            pdk.Layer("ScatterplotLayer", [
                {"pos": [p_coords['lon'], p_coords['lat']], "name": "Pickup"},
                {"pos": [d_coords['lon'], d_coords['lat']], "name": "Dropoff"}
            ], get_position="pos", get_color=[255, 75, 75], get_radius=200)
        ]
    ))

# --- 6. PRÉDICTION VIA API ---
if eval_click:
    api_url = f"{st.secrets['url_base'].rstrip('/')}/predict"
    # Formatage strict pour ton modèle : %Y-%m-%d %H:%M:%S
    pickup_dt_str = f"{sel_date} {sel_time.strftime('%H:%M:%S')}"

    params = {
        "pickup_datetime": pickup_dt_str,
        "pickup_longitude": float(p_coords['lon']),
        "pickup_latitude": float(p_coords['lat']),
        "dropoff_longitude": float(d_coords['lon']),
        "dropoff_latitude": float(d_coords['lat']),
        "passenger_count": int(passengers)
    }

    with st.spinner("Appel à l'API de prédiction..."):
        try:
            r = requests.get(api_url, params=params, timeout=10)
            if r.status_code == 200:
                st.session_state.current_fare = r.json().get("fare", 0.0)
                st.session_state.fare_calculated = True
                st.rerun()
            else:
                st.error(f"Erreur API ({r.status_code}) : {r.text}")
        except Exception as e:
            st.error(f"Erreur de connexion : {e}")

# Affichage du résultat final
if st.session_state.fare_calculated:
    with left_col:
        btn_area.success(f"### 💰 Tarif Estimé : ${st.session_state.current_fare:.2f}")
        if st.button("Recommencer"):
            st.session_state.fare_calculated = False
            st.session_state.ordered = False
            st.rerun()
