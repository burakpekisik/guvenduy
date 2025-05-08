import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
import time
from config import API_URL, APP_TITLE, APP_ICON
import folium
from streamlit_folium import folium_static

# Cache mekanizması için fonksiyon dekoratörleri
@st.cache_data(ttl=300)  # 5 dakika boyunca önbellekte tut
def cached_api_request(endpoint, method="GET", data=None):
    """API isteklerini önbelleğe alan fonksiyon"""
    headers = {}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    
    url = f"{API_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=data)
            if response.status_code == 200:
                return response.json()
            return None
        else:
            # POST, PUT, DELETE istekleri için cache kullanma
            return None
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

@st.cache_resource
def create_base_map(location, zoom):
    """Harita oluşturmayı önbelleğe alan fonksiyon"""
    m = folium.Map(location=location, zoom_start=zoom)
    return m

# Configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session state for authentication
if 'token' not in st.session_state:
    st.session_state.token = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# Authentication Functions
def login(username, password):
    try:
        response = requests.post(
            f"{API_URL}/auth/token",
            data={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            st.session_state.username = username
            
            # Get user info to check admin status
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            user_response = requests.get(f"{API_URL}/auth/me", headers=headers)
            if user_response.status_code == 200:
                user_data = user_response.json()
                st.session_state.is_admin = user_data["privilege"] in ["admin", "super_admin"]
            
            return True
        else:
            return False
    except Exception as e:
        st.error(f"Error during login: {str(e)}")
        return False

def logout():
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.is_admin = False

# API Request Helper with Authorization
def api_request(endpoint, method="GET", data=None, files=None):
    headers = {}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    
    url = f"{API_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=data)
        elif method == "POST":
            if files:
                response = requests.post(url, headers=headers, data=data, files=files)
            else:
                response = requests.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
            
        return response
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

# Helper function to handle API failures gracefully
def safe_get_json(response, default_value=None):
    """
    Safely extracts JSON from a response, returning a default value if the 
    response is None, not 2xx, or not valid JSON
    """
    if not response or response.status_code >= 300:
        return default_value
    
    try:
        return response.json()
    except Exception:
        return default_value

# Sidebar Navigation
def render_sidebar():
    st.sidebar.title("📊 Sound Classification")
    
    if st.session_state.token:
        st.sidebar.text(f"Logged in as: {st.session_state.username}")
        
        # Navigation Links
        page = st.sidebar.radio(
            "Navigate", 
            ["Dashboard", "Sound Predictions", "Evaluations", "Alert System", "User Management"]
        )
        
        if st.sidebar.button("Logout"):
            logout()
            st.rerun()
            
        return page
    else:
        return "Login"

# Pages
def login_page():
    st.title("🔒 Admin Login")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if login(username, password):
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    with col2:
        st.markdown("""
        ## Welcome to Sound Classification Admin Panel
        
        This administrative interface allows you to:
        
        - Monitor sound predictions
        - Review evaluation metrics
        - Manage alert classifications
        - Administer user accounts
        
        Please login with your admin credentials to access the system.
        """)

def dashboard_page():
    st.title("📈 Dashboard")
    
    # Layout with multiple metrics
    col1, col2, col3 = st.columns(3)
    
    # Fetch stats from API using the cached API request
    predictions_data = cached_api_request("/audio/predictions") or {"count": 0, "predictions": []}
    evaluation_data = cached_api_request("/audio/evaluations/stats") or {"total_evaluations": 0, "overall_success_rate": 0}
    alerts_data = cached_api_request("/alerts/classes") or []
    
    with col1:
        st.metric("Total Predictions", predictions_data.get("count", 0))
    
    with col2:
        success_rate = evaluation_data.get("overall_success_rate", 0) * 100
        st.metric("Evaluation Success Rate", f"{success_rate:.1f}%")
    
    with col3:
        st.metric("Active Alert Classes", len(alerts_data))
    
    # Charts
    st.subheader("Prediction Distribution")
    if "class_distribution" in evaluation_data and evaluation_data["class_distribution"]:
        try:
            df = pd.DataFrame(evaluation_data["class_distribution"])
            fig = px.pie(df, values="count", names="class_name", title="Sound Class Distribution")
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not display prediction distribution chart: {str(e)}")
    else:
        st.info("No class distribution data available")
    
    # Recent activity
    st.subheader("Recent Predictions")
    if "predictions" in predictions_data and predictions_data["predictions"]:
        try:
            recent_preds = predictions_data["predictions"][:5]  # Show last 5
            
            if recent_preds:
                df_recent = pd.DataFrame(recent_preds)
                df_recent["created_at"] = pd.to_datetime(df_recent["created_at"])
                df_recent["created_at"] = df_recent["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
                
                columns_to_show = [col for col in ["file_name", "highest_class", "highest_confidence", "created_at"] 
                                   if col in df_recent.columns]
                st.dataframe(df_recent[columns_to_show], use_container_width=True)
        except Exception as e:
            st.warning(f"Could not display recent predictions: {str(e)}")
    else:
        st.info("No recent predictions available")

def sound_predictions_page():
    st.title("🔊 Sound Predictions")
    
    # Upload new sound for prediction
    st.subheader("Upload Sound for Prediction")
    uploaded_file = st.file_uploader("Choose a WAV file", type=["wav"])
    
    if uploaded_file:
        if st.button("Process Sound"):
            with st.spinner("Processing..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "audio/wav")}
                response = api_request("/audio/predict", method="POST", files=files)
                
                if response and response.status_code == 200:
                    result = safe_get_json(response, {"predictions": {}})
                    
                    st.success("Sound processed successfully!")
                    
                    # Display predictions
                    predictions = result.get("predictions", {})
                    if predictions:
                        df_pred = pd.DataFrame(list(predictions.items()), columns=["Class", "Confidence"])
                        df_pred = df_pred.sort_values("Confidence", ascending=False)
                        
                        # Bar chart of predictions
                        fig = px.bar(df_pred, x="Class", y="Confidence", 
                                     title=f"Prediction Results for {uploaded_file.name}")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Table of all predictions
                        st.dataframe(df_pred, use_container_width=True)
                    else:
                        st.warning("No prediction results returned")
                else:
                    st.error("Failed to process sound file")
    
    # Recent predictions list
    st.subheader("Recent Predictions")
    limit = st.slider("Number of predictions to show", 10, 100, 20)
    
    # Use cached predictions if available, otherwise use regular API request
    if 'predictions_data' not in st.session_state or st.button("Refresh Predictions"):
        with st.spinner("Loading..."):
            # Try to get from cache first
            cached_data = cached_api_request(f"/audio/predictions?limit={limit}")
            if cached_data:
                st.session_state.predictions_data = cached_data
            else:
                # Fallback to regular API request
                response = api_request(f"/audio/predictions?limit={limit}")
                if response:
                    st.session_state.predictions_data = safe_get_json(response, {"count": 0, "predictions": []})
    
    # Use the data from session state
    data = st.session_state.get('predictions_data', {"count": 0, "predictions": []})
    predictions = data.get("predictions", [])
    
    if predictions:
        try:
            df = pd.DataFrame(predictions)
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Add audio player column - lazily render audio player only when needed
            df["audio_player"] = df.apply(
                lambda row: f"<a href='#' onclick=\"playAudio('{row['file_path']}');\">🔊 Play</a>", 
                axis=1
            )
            
            # Only display columns that exist
            columns_to_show = [col for col in ["id", "file_name", "highest_class", "highest_confidence", "created_at", "audio_player"] 
                              if col in df.columns]
            
            # Display dataframe with HTML
            st.markdown(
                """
                <script>
                function playAudio(file_path) {
                    // Create hidden audio element if it doesn't exist
                    if (!document.getElementById('audio-player')) {
                        const audio = document.createElement('audio');
                        audio.id = 'audio-player';
                        audio.controls = true;
                        audio.style.display = 'block';
                        audio.style.margin = '10px auto';
                        document.body.appendChild(audio);
                    }
                    
                    // Set the audio source and play
                    const audioPlayer = document.getElementById('audio-player');
                    audioPlayer.src = '""" + API_URL + """/audio/file/' + file_path;
                    audioPlayer.play();
                    
                    // Scroll to audio player
                    audioPlayer.scrollIntoView();
                    
                    return false;
                }
                </script>
                """,
                unsafe_allow_html=True
            )
            
            # Convert dataframe to HTML with custom styling
            st.write(df[columns_to_show].to_html(escape=False, index=False), unsafe_allow_html=True)
            
            # Add Audio Player Element
            st.subheader("Audio Player")
            st.info("Click on 🔊 Play link next to any prediction to listen to the audio")
            
        except Exception as e:
            st.warning(f"Error displaying predictions: {str(e)}")
    else:
        st.info("No predictions found")

def evaluations_page():
    st.title("📋 Evaluation Statistics")
    
    # Add manual reload button due to backend issues
    if st.button("Reload Evaluation Statistics"):
        # Cache'i temizle ve sayfayı yeniden yükle
        st.cache_data.clear()
        st.rerun()
    
    # Fetch evaluation statistics - önbellekli API isteği kullan
    stats = cached_api_request("/audio/evaluations/stats") or {
        "total_evaluations": 0,
        "overall_success_rate": 0,
        "class_distribution": [],
        "class_success_rates": []
    }
    
    # Display overall stats
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Evaluations", stats.get("total_evaluations", 0))
    
    with col2:
        success_rate = stats.get("overall_success_rate", 0) * 100
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    with col3:
        st.metric("Total Classes", len(stats.get("class_distribution", [])))
    
    # Class distribution
    st.subheader("Evaluations by Sound Class")
    
    if "class_distribution" in stats and stats["class_distribution"]:
        try:
            class_df = pd.DataFrame(stats["class_distribution"])
            
            # Create pie chart
            fig1 = px.pie(
                class_df, 
                values="count", 
                names="class_name",
                title="Distribution of Evaluations by Sound Class"
            )
            st.plotly_chart(fig1, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not display class distribution chart: {str(e)}")
    else:
        st.info("No class distribution data available")
    
    # Success rate by class
    st.subheader("Success Rate by Sound Class")
    
    if "class_success_rates" in stats and stats["class_success_rates"]:
        try:
            success_df = pd.DataFrame(stats["class_success_rates"])
            success_df["success_rate"] = success_df["success_rate"] * 100  # Convert to percentage
            
            # Create bar chart
            fig2 = px.bar(
                success_df,
                x="class_name",
                y="success_rate",
                title="Success Rate by Sound Class (%)",
                labels={"success_rate": "Success Rate (%)", "class_name": "Sound Class"}
            )
            st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not display success rate chart: {str(e)}")
    else:
        st.info("No class success rate data available")

def alert_system_page():
    st.title("🚨 Alert System")
    
    # Initialize session state variables for map interaction if they don't exist
    if 'selected_location' not in st.session_state:
        st.session_state.selected_location = (39.925533, 32.866287)  # Ankara merkez (varsayılan)
    if 'map_center' not in st.session_state:
        st.session_state.map_center = (39.925533, 32.866287)  # Ankara merkez (varsayılan)
    if 'map_zoom' not in st.session_state:
        st.session_state.map_zoom = 6
    if 'clicked_location' not in st.session_state:
        st.session_state.clicked_location = None
    
    # Create tabs for different alert system features
    tab1, tab2, tab3 = st.tabs(["Notifiable Classes", "View Alerts", "Create Alert"])
    
    # Tab 1: Notifiable Classes Management
    with tab1:
        st.subheader("Notifiable Sound Classes")
        
        # Only admins can add/edit classes
        if st.session_state.is_admin:
            with st.expander("Add New Notifiable Class", expanded=False):
                with st.form("add_class_form"):
                    class_name = st.text_input("Class Name")
                    description = st.text_area("Description")
                    min_confidence = st.slider("Minimum Confidence Threshold", 0.0, 1.0, 0.7, 0.01)
                    
                    submit = st.form_submit_button("Add Class")
                    
                    if submit:
                        if class_name.strip():
                            data = {
                                "class_name": class_name,
                                "description": description,
                                "min_confidence": min_confidence
                            }
                            
                            response = api_request("/alerts/classes", method="POST", data=data)
                            
                            if response and response.status_code == 201:
                                st.success(f"Notifiable class '{class_name}' added successfully!")
                            else:
                                st.error("Failed to add notifiable class")
                        else:
                            st.error("Class name is required")
        
        # List of existing classes (for all users)
        response = api_request("/alerts/classes", data={"include_inactive": st.session_state.is_admin})
        
        if response and response.status_code == 200:
            classes = safe_get_json(response, [])
            
            if classes:
                df = pd.DataFrame(classes)
                
                # Format datetime and other columns
                if "created_at" in df.columns:
                    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                
                st.dataframe(
                    df[["id", "class_name", "description", "min_confidence", "is_active", "created_at"]],
                    use_container_width=True
                )
                
                # Edit class (admin only)
                if st.session_state.is_admin:
                    st.subheader("Update Notifiable Class")
                    
                    class_id = st.selectbox(
                        "Select Class to Update",
                        options=df["id"].tolist(),
                        format_func=lambda x: df[df["id"] == x]["class_name"].iloc[0]
                    )
                    
                    if class_id:
                        selected_class = df[df["id"] == class_id].iloc[0]
                        
                        with st.form("update_class_form"):
                            description = st.text_area("Description", value=selected_class["description"])
                            min_confidence = st.slider(
                                "Minimum Confidence Threshold", 
                                0.0, 1.0, float(selected_class["min_confidence"]), 0.01
                            )
                            is_active = st.checkbox("Active", value=selected_class["is_active"])
                            
                            update_submit = st.form_submit_button("Update Class")
                            
                            if update_submit:
                                data = {
                                    "description": description,
                                    "min_confidence": min_confidence,
                                    "is_active": is_active
                                }
                                
                                response = api_request(f"/alerts/classes/{class_id}", method="PUT", data=data)
                                
                                if response and response.status_code == 200:
                                    st.success("Class updated successfully!")
                                else:
                                    st.error("Failed to update class")
            else:
                st.info("No notifiable classes found")
        else:
            st.error("Failed to load notifiable classes")
    
    # Tab 2: View Alerts
    with tab2:
        st.subheader("Recent Alerts")
        
        # Get notifiable classes for filtering using cache
        classes = cached_api_request("/alerts/classes") or []
        
        if not classes:
            st.warning("No notifiable classes found. Please create at least one class.")
        else:
            class_options = {c["id"]: c["class_name"] for c in classes}
            
            # Create columns for layout
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Interactive map for location selection - önbelleklenmiş harita oluşturucuyu kullan
                st.subheader("Select Location on Map")
                
                # Create interactive map with folium
                m = create_base_map(st.session_state.map_center, st.session_state.map_zoom)
                
                # Add a marker for the currently selected location
                folium.Marker(
                    location=st.session_state.selected_location,
                    popup="Selected Location",
                    icon=folium.Icon(color="red", icon="info-sign")
                ).add_to(m)
                
                # Add click event to folium map
                m.add_child(folium.LatLngPopup())
                
                # Display the map with increased width
                folium_static(m, width=600, height=400)
                
                # Add manual input button below map
                st.write("Haritada istediğiniz konumu seçin veya koordinatları manuel girin.")
                
                # Use a form for coordinate updates
                with st.form("map_coord_form_view"):
                    col_lat, col_lng = st.columns(2)
                    with col_lat:
                        manual_lat = st.number_input("Manuel Latitude:", value=st.session_state.selected_location[0], format="%.6f")
                    with col_lng:
                        manual_lng = st.number_input("Manuel Longitude:", value=st.session_state.selected_location[1], format="%.6f")
                    
                    update_map = st.form_submit_button("Konumu Güncelle")
                    
                    if update_map:
                        st.session_state.selected_location = (manual_lat, manual_lng)
                        st.session_state.map_center = (manual_lat, manual_lng)
                        st.rerun()
            
            with col2:
                # Form for search parameters
                st.subheader("Search Parameters")
                
                latitude = st.number_input("Latitude", value=st.session_state.selected_location[0], format="%.6f")
                longitude = st.number_input("Longitude", value=st.session_state.selected_location[1], format="%.6f")
                radius = st.number_input("Radius (km)", value=10.0, min_value=0.1, max_value=100.0)
                hours_ago = st.slider("Hours ago", 1, 48, 24)
                
                selected_classes = st.multiselect(
                    "Filter by Classes",
                    options=list(class_options.keys()),
                    format_func=lambda x: class_options[x]
                )
            
            # Button to fetch alerts
            if st.button("Fetch Alerts"):
                # Update session state with form values
                st.session_state.selected_location = (latitude, longitude)
                
                # Prepare parameters for API request
                params = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_km": radius,
                    "hours_ago": hours_ago
                }
                
                if selected_classes:
                    params["class_ids"] = selected_classes
                
                # Fetch alerts
                response = api_request("/alerts/nearby", data=params)
                
                if response and response.status_code == 200:
                    alerts = safe_get_json(response, [])
                    
                    if alerts:
                        df = pd.DataFrame(alerts)
                        
                        # Format datetime columns
                        for col in ["created_at", "expires_at"]:
                            if col in df.columns:
                                df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Add class name from ID
                        df["class_name"] = df["class_id"].apply(lambda x: class_options.get(x, "Unknown"))
                        
                        # Map visualization with folium (better map)
                        st.subheader("Alert Locations")
                        
                        # Create map with selected location as center
                        alert_map = folium.Map(location=st.session_state.selected_location, zoom_start=10)
                        
                        # Add a marker for search center
                        folium.Marker(
                            location=st.session_state.selected_location,
                            popup="Search Center",
                            icon=folium.Icon(color="blue", icon="search")
                        ).add_to(alert_map)
                        
                        # Add circle for the search radius
                        folium.Circle(
                            location=st.session_state.selected_location,
                            radius=radius * 1000,  # Convert km to meters
                            color="blue",
                            fill=True,
                            fill_opacity=0.1
                        ).add_to(alert_map)
                        
                        # Add markers for each alert
                        for i, row in df.iterrows():
                            tooltip = f"{row['class_name']} ({row['confidence']:.2f})"
                            popup_content = f"""
                            <b>Alert ID:</b> {row['id']}<br>
                            <b>Class:</b> {row['class_name']}<br>
                            <b>Confidence:</b> {row['confidence']:.2f}<br>
                            <b>Created:</b> {row['created_at']}<br>
                            <b>Distance:</b> {row.get('distance_km', 'N/A')} km
                            """
                            
                            folium.Marker(
                                location=[row["latitude"], row["longitude"]],
                                tooltip=tooltip,
                                popup=folium.Popup(popup_content, max_width=300),
                                icon=folium.Icon(
                                    color="red",
                                    icon="warning-sign"
                                )
                            ).add_to(alert_map)
                        
                        # Display the map
                        folium_static(alert_map, width=800, height=500)
                        
                        # Alert table
                        st.subheader("Alert Details")
                        
                        # Add distance information if available
                        if "distance_km" in df.columns:
                            df["distance_km"] = df["distance_km"].apply(lambda x: f"{x:.2f} km")
                        
                        # Select columns to display
                        display_cols = ["id", "class_name", "confidence", "distance_km", "created_at"]
                        display_cols = [col for col in display_cols if col in df.columns]
                        
                        st.dataframe(df[display_cols], use_container_width=True)
                    else:
                        st.info("No alerts found in the specified area and timeframe")
                else:
                    st.error("Failed to fetch alerts")
    
    # Tab 3: Create Alert (for testing and manual creation)
    with tab3:
        if not st.session_state.is_admin:
            st.warning("You need administrator privileges to create manual alerts.")
            return
            
        st.subheader("Create New Alert")
        
        # Get notifiable classes
        response = api_request("/alerts/classes")
        classes = safe_get_json(response, [])
        
        if not classes:
            st.warning("No notifiable classes found. Please create at least one class first.")
        else:
            class_options = {c["id"]: c["class_name"] for c in classes}
            
            # Create columns for layout
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Interactive map for location selection
                st.subheader("Select Location on Map")
                
                # Create interactive map with folium
                m = create_base_map(st.session_state.map_center, st.session_state.map_zoom)
                
                # Add a marker for the currently selected location
                folium.Marker(
                    location=st.session_state.selected_location,
                    popup="Selected Location",
                    icon=folium.Icon(color="green", icon="info-sign")
                ).add_to(m)
                
                # Add click event to folium map
                m.add_child(folium.LatLngPopup())
                
                # Display the map with increased width
                folium_static(m, width=600, height=400)
                
                # Add manual input button below map
                st.write("Haritada istediğiniz konumu seçin veya koordinatları manuel girin.")
                
                # Use a form for coordinate updates
                with st.form("map_coord_form_create"):
                    col_lat, col_lng = st.columns(2)
                    with col_lat:
                        manual_lat = st.number_input("Manuel Latitude:", value=st.session_state.selected_location[0], format="%.6f")
                    with col_lng:
                        manual_lng = st.number_input("Manuel Longitude:", value=st.session_state.selected_location[1], format="%.6f")
                    
                    update_map = st.form_submit_button("Konumu Güncelle")
                    
                    if update_map:
                        st.session_state.selected_location = (manual_lat, manual_lng)
                        st.session_state.map_center = (manual_lat, manual_lng)
                        st.rerun()
            
            with col2:
                # Form for alert creation
                with st.form("create_alert_form"):
                    class_id = st.selectbox(
                        "Alert Class",
                        options=list(class_options.keys()),
                        format_func=lambda x: class_options[x]
                    )
                    
                    latitude = st.number_input("Latitude", value=st.session_state.selected_location[0], format="%.6f")
                    longitude = st.number_input("Longitude", value=st.session_state.selected_location[1], format="%.6f")
                    confidence = st.slider("Confidence", 0.0, 1.0, 0.8, 0.01)
                    device_id = st.text_input("Device ID", value="admin-manual-alert")
                    
                    # Hours until expiration
                    hours_valid = st.number_input("Hours Valid", value=24, min_value=1, max_value=72)
                    
                    create_submit = st.form_submit_button("Create Alert")
                    
                    if create_submit:
                        # Create alert payload
                        data = {
                            "class_id": class_id,
                            "latitude": latitude,
                            "longitude": longitude,
                            "confidence": confidence,
                            "device_id": device_id,
                            "hours_valid": hours_valid
                        }
                        
                        # Make API request to create alert
                        response = api_request("/alerts/create", method="POST", data=data)
                        
                        if response and response.status_code in [200, 201]:
                            st.success(f"Alert created successfully for {class_options[class_id]}!")
                            
                            # Update selected location
                            st.session_state.selected_location = (latitude, longitude)
                        else:
                            st.error("Failed to create alert")

def user_management_page():
    st.title("👥 User Management")
    
    # Only accessible to admins
    if not st.session_state.is_admin:
        st.warning("You need administrator privileges to access this page.")
        return
    
    # Create tabs for different user management features
    tab1, tab2, tab3 = st.tabs(["User List", "Update User", "Delete User"])
    
    # Get users from the API
    response = api_request("/auth/users")
    
    if response and response.status_code == 200:
        users = safe_get_json(response, [])
        
        # Tab 1: User List & Privilege Management
        with tab1:
            # Display users table
            if users:
                df = pd.DataFrame(users)
                
                if "created_at" in df.columns:
                    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                
                # Remove password hash from display
                if "password_hash" in df.columns:
                    df = df.drop(columns=["password_hash"])
                
                st.dataframe(df, use_container_width=True)
                
                # User privilege management
                st.subheader("Update User Privileges")
                
                user_id = st.selectbox(
                    "Select User",
                    options=df["id"].tolist(),
                    format_func=lambda x: df[df["id"] == x]["username"].iloc[0],
                    key="privilege_user_select"
                )
                
                if user_id:
                    selected_user = df[df["id"] == user_id].iloc[0]
                    
                    with st.form("update_privilege_form"):
                        privilege = st.selectbox(
                            "Privilege Level",
                            options=["user", "admin", "super_admin"],
                            index=["user", "admin", "super_admin"].index(selected_user.get("privilege", "user"))
                        )
                        
                        submit = st.form_submit_button("Update Privilege")
                        
                        if submit:
                            data = {"privilege": privilege}
                            response = api_request(f"/auth/users/{user_id}/privilege", method="PUT", data=data)
                            
                            if response and response.status_code == 200:
                                st.success(f"User privileges updated successfully!")
                                # Clear cache and reload the page to show updated data
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("Failed to update user privileges")
            else:
                st.info("No users found")
        
        # Tab 2: Update User Information
        with tab2:
            st.subheader("Update User Information")
            
            if users:
                user_id = st.selectbox(
                    "Select User to Update",
                    options=df["id"].tolist(),
                    format_func=lambda x: df[df["id"] == x]["username"].iloc[0],
                    key="update_user_select"
                )
                
                if user_id:
                    selected_user = df[df["id"] == user_id].iloc[0]
                    
                    with st.form("update_user_form"):
                        username = st.text_input("Username", value=selected_user["username"])
                        email = st.text_input("Email", value=selected_user["email"])
                        
                        # Password is optional for updates - blank means don't change
                        st.write("Leave password blank to keep current password")
                        password = st.text_input("New Password (optional)", type="password")
                        
                        update_submit = st.form_submit_button("Update User")
                        
                        if update_submit:
                            # Only send non-empty values to API - empty password means no change
                            data = {
                                "username": username,
                                "email": email
                            }
                            
                            # Only include password if provided
                            if password:
                                data["password"] = password
                            
                            # Make API request to update user
                            response = api_request(f"/auth/users/{user_id}", method="PUT", data=data)
                            
                            if response and response.status_code == 200:
                                st.success(f"User '{username}' updated successfully!")
                                # Clear cache and reload the page to show updated data
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                error_detail = "Unknown error"
                                if response:
                                    try:
                                        error_data = response.json()
                                        error_detail = error_data.get("detail", "Unknown error")
                                    except:
                                        error_detail = f"Status code: {response.status_code}"
                                
                                st.error(f"Failed to update user: {error_detail}")
            else:
                st.info("No users found to update")
        
        # Tab 3: Delete User
        with tab3:
            st.subheader("Delete User")
            
            if users:
                current_username = st.session_state.username
                # Filter out the current user - can't delete yourself
                filtered_users = [u for u in users if u["username"] != current_username]
                
                if filtered_users:
                    user_ids = [u["id"] for u in filtered_users]
                    user_usernames = [u["username"] for u in filtered_users]
                    
                    user_index = st.selectbox(
                        "Select User to Delete",
                        options=range(len(user_ids)),
                        format_func=lambda i: user_usernames[i],
                        key="delete_user_select"
                    )
                    
                    selected_user_id = user_ids[user_index]
                    selected_username = user_usernames[user_index]
                    
                    st.warning(f"⚠️ WARNING: Deleting a user is permanent and cannot be undone!")
                    
                    # Confirmation with username typing
                    st.write(f"Type '{selected_username}' to confirm deletion:")
                    confirmation = st.text_input("Confirmation", key="delete_confirmation")
                    
                    if st.button("Delete User", type="primary", help="This will permanently delete the user"):
                        if confirmation == selected_username:
                            # Make API request to delete user
                            response = api_request(f"/auth/users/{selected_user_id}", method="DELETE")
                            
                            if response and response.status_code == 200:
                                st.success(f"User '{selected_username}' has been deleted successfully!")
                                # Clear cache and reload the page to show updated data
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                error_detail = "Unknown error"
                                if response:
                                    try:
                                        error_data = response.json()
                                        error_detail = error_data.get("detail", "Unknown error")
                                    except:
                                        error_detail = f"Status code: {response.status_code}"
                                
                                st.error(f"Failed to delete user: {error_detail}")
                        else:
                            st.error("Confirmation text doesn't match the username. Please try again.")
                else:
                    st.info("No users available to delete (you cannot delete your own account)")
            else:
                st.info("No users found to delete")
    else:
        st.warning("Could not retrieve user list. Please make sure the API is running and you have administrative privileges.")

# Main App
def main():
    page = render_sidebar()
    
    if page == "Login":
        login_page()
    elif page == "Dashboard":
        dashboard_page()
    elif page == "Sound Predictions":
        sound_predictions_page()
    elif page == "Evaluations":
        evaluations_page()
    elif page == "Alert System":
        alert_system_page()
    elif page == "User Management":
        user_management_page()

if __name__ == "__main__":
    main()