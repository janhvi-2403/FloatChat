import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
from datetime import datetime, timedelta

# Constants
API_BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="FloatChat: Ocean Argo Data",
    page_icon="🌊",
    layout="wide"
)

# Custom CSS for aesthetics
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌊 FloatChat: Argo Float Data Dashboard")
st.markdown("Explore real-time and historical oceanographic data from Argo floats globally.")

# Sidebar Filters
st.sidebar.header("🔍 Search Parameters")
st.sidebar.markdown("Define your search bounding box (latitude and longitude).")

col_lon, col_lat = st.sidebar.columns(2)
with col_lon:
    lon_min = st.number_input("Min Lon", value=-70.0, step=1.0)
    lon_max = st.number_input("Max Lon", value=-60.0, step=1.0)
with col_lat:
    lat_min = st.number_input("Min Lat", value=30.0, step=1.0)
    lat_max = st.number_input("Max Lat", value=40.0, step=1.0)

st.sidebar.markdown("Define time and depth ranges.")
col_date1, col_date2 = st.sidebar.columns(2)
with col_date1:
    time_start = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
with col_date2:
    time_end = st.date_input("End Date", value=datetime.today())

depth_range = st.sidebar.slider(
    "Depth Range (m)",
    min_value=0, max_value=2000, value=(0, 2000)
)

fetch_btn = st.sidebar.button("🚀 Fetch Data", type="primary")

# Backend Health/Cache Check
def get_backend_status():
    try:
        res = requests.get(f"{API_BASE_URL}/health/ready", timeout=2)
        if res.status_code == 200:
            return True
    except:
        return False
    return False

if not get_backend_status():
    st.error("⚠️ Backend API is currently unreachable. Please check if the backend server is running.")
else:
    if fetch_btn:
        with st.spinner("Fetching data from backend API..."):
            payload = {
                "lon_min": float(lon_min),
                "lon_max": float(lon_max),
                "lat_min": float(lat_min),
                "lat_max": float(lat_max),
                "time_start": time_start.strftime("%Y-%m-%d"),
                "time_end": time_end.strftime("%Y-%m-%d"),
                "depth_min": float(depth_range[0]),
                "depth_max": float(depth_range[1])
            }
            
            try:
                response = requests.post(f"{API_BASE_URL}/api/data/region", json=payload)
                if response.status_code == 200:
                    result = response.json()
                    data = result.get("data", {})
                    profiles = data.get("profiles", [])
                    metadata = data.get("metadata", {})
                    cache_status = result.get("cache_status", "unknown")
                    
                    if not profiles:
                        st.warning("No float profiles found for the given criteria.")
                    else:
                        st.success(f"Successfully retrieved {len(profiles)} profiles! (Cache: {cache_status})")
                        
                        # --- Metrics Overview ---
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Total Profiles", data.get("num_profiles", 0))
                        m2.metric("Unique Floats", len(data.get("floats", [])))
                        m3.metric("Data Source", metadata.get("source", "GDAC").upper())
                        m4.metric("Cache Status", cache_status.upper())
                        
                        st.markdown("---")
                        
                        # Data Prep
                        df = pd.DataFrame(profiles)
                        
                        map_col, chart_col = st.columns([1, 1])
                        
                        with map_col:
                            st.subheader("🗺️ Float Locations")
                            # Create map centered on average coordinates
                            avg_lat = df['latitude'].mean()
                            avg_lon = df['longitude'].mean()
                            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=4)
                            
                            for _, row in df.iterrows():
                                if pd.notnull(row['latitude']) and pd.notnull(row['longitude']):
                                    folium.CircleMarker(
                                        location=[row['latitude'], row['longitude']],
                                        radius=5,
                                        popup=f"Float: {row['float_id']}<br>Date: {row['date']}",
                                        color="blue",
                                        fill=True,
                                        fillOpacity=0.6
                                    ).add_to(m)
                                    
                            st_folium(m, height=400, width=700)
                            
                        with chart_col:
                            st.subheader("📊 Data Visualization")
                            
                            # Expand arrays for plotting (take first profile for demo or aggregate)
                            # To keep it simple, we'll plot a scatter of Temp/Salinity vs Depth for all retrieved points.
                            
                            # Flattening the data for plotting
                            plot_data = []
                            for p in profiles:
                                if 'temperature' in p and 'pressure' in p and 'salinity' in p:
                                    temps = p['temperature']
                                    pressures = p['pressure']
                                    sals = p['salinity']
                                    # Ensure they are equal length
                                    min_len = min(len(temps), len(pressures), len(sals))
                                    for i in range(min_len):
                                        plot_data.append({
                                            'Float': p['float_id'],
                                            'Pressure (dbar)': pressures[i],
                                            'Temperature (°C)': temps[i],
                                            'Salinity (PSU)': sals[i]
                                        })
                            
                            if plot_data:
                                plot_df = pd.DataFrame(plot_data)
                                
                                tab1, tab2 = st.tabs(["Temperature Profile", "Salinity Profile"])
                                
                                with tab1:
                                    fig_temp = px.scatter(
                                        plot_df, x="Temperature (°C)", y="Pressure (dbar)", 
                                        color="Float",
                                        title="Temperature vs Depth"
                                    )
                                    fig_temp.update_yaxes(autorange="reversed") # Depth goes down
                                    st.plotly_chart(fig_temp, use_container_width=True)
                                
                                with tab2:
                                    fig_sal = px.scatter(
                                        plot_df, x="Salinity (PSU)", y="Pressure (dbar)", 
                                        color="Float",
                                        title="Salinity vs Depth"
                                    )
                                    fig_sal.update_yaxes(autorange="reversed")
                                    st.plotly_chart(fig_sal, use_container_width=True)
                            else:
                                st.info("No detailed sensor data (temp/salinity/pressure) available for these profiles.")
                                
                        st.markdown("---")
                        st.subheader("📋 Raw Data Explorer")
                        display_df = df[['float_id', 'date', 'latitude', 'longitude']].copy()
                        display_df['date'] = pd.to_datetime(display_df['date'])
                        st.dataframe(display_df, use_container_width=True)
                        
            except Exception as e:
                st.error(f"Error fetching data: {str(e)}")
