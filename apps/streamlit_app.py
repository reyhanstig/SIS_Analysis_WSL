import streamlit as st
import pandas as pd
import plotly.express as px

# Fix path resolution for scripts/ folder
try:
    from utils.paths import ProjectPaths
except ImportError:
    from utils.paths import ProjectPaths

# Set page config
st.set_page_config(page_title="SIS Time-Series Dashboard", layout="wide")

st.title("🌊 Water Quality Time-Series Dashboard")

# Function to load data (cached for performance)
@st.cache_data
def load_data():
    df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    
    # Create a proper datetime column
    if 'survey_ym' in df.columns:
        df['date'] = pd.to_datetime(df['survey_ym'], format='%Y%m', errors='coerce')
    else:
        df['date'] = pd.to_datetime(df[['surveyyear', 'surveymont']].assign(DAY=1).rename(columns={'surveyyear': 'year', 'surveymont': 'month'}))
        
    # Ensure latitude and longitude are float
    if 'latitude' in df.columns:
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    
    # Ensure year column is numeric
    if 'year' in df.columns:
        df['year'] = pd.to_numeric(df['year'], errors='coerce')
        
    return df

with st.spinner("Loading dataset... This may take a few seconds on first load."):
    df = load_data()

# --- Initialize Defaults for first run ---
if 'stations_pane_1' not in st.session_state:
    st.session_state['stations_pane_1'] = ['00040636', '00040632', '00040620', '00040617']

# --- Sidebar Controls ---
st.sidebar.header("🌍 Global Filters")

# 1. Filter by Watermass
watermass_options = df['watermass_name'].dropna().unique().tolist()
selected_watermass = st.sidebar.selectbox("Select Watermass", options=["All"] + watermass_options, index=0)

if selected_watermass != "All":
    filtered_df = df[df['watermass_name'] == selected_watermass]
else:
    filtered_df = df

# 2. Filter by Division (Sub-region)
division_options = filtered_df['division'].dropna().unique().tolist()
selected_division = st.sidebar.selectbox("Select Division", options=["All"] + division_options, index=0)

if selected_division != "All":
    filtered_df = filtered_df[filtered_df['division'] == selected_division]

# 3. Filter by Year Range
min_year = int(df['year'].min())
max_year = int(df['year'].max())
selected_year_range = st.sidebar.slider("Select Year Range", min_year, max_year, (min_year, max_year))

# 4. Filter by Season
season_options = sorted(filtered_df['season'].dropna().unique().tolist())
try:
    season_index = ["All"] + season_options
    default_season_idx = season_index.index('Summer') if 'Summer' in season_index else 0
except ValueError:
    default_season_idx = 0
selected_season = st.sidebar.selectbox("Select Season", options=["All"] + season_options, index=default_season_idx)

# 5. Filter by Depth Layer (saisuipoin)
depth_layer_options = sorted(filtered_df['saisuipoin'].dropna().unique().tolist())
try:
    default_layer_idx = depth_layer_options.index(2) if 2 in depth_layer_options else 0
except ValueError:
    default_layer_idx = 0
selected_layer = st.sidebar.selectbox("Select Depth Layer (saisuipoin)", options=depth_layer_options, index=default_layer_idx)

# 6. Select Parameter
all_params = [
    'temp', 'color', 'clearness', 'wtemp', 'ph', 'ph2', 'do_', 'do_2', 
    'salt', 'salt2', 'cod', 'cod2', 'rcod', 'rcod2', 'nh4n', 'nh4n2', 
    'no2n', 'no2n2', 'no3n', 'no3n2', 'tn', 'tn2', 'po4p', 'po4p2', 
    'tp', 'tp2', 'chlorophyl', 'chloroph_1', 'feiochin', 'feiochin2', 
    'toc', 'toc2', 'doc', 'doc2'
]
available_params = [p for p in all_params if p in df.columns]
try:
    default_param_idx = available_params.index('do_2') if 'do_2' in available_params else 0
except ValueError:
    default_param_idx = 0
selected_param = st.sidebar.selectbox("Select Parameter to Plot", options=available_params, index=default_param_idx)

# --- ENSURE NUMERIC TYPE ---
df[selected_param] = pd.to_numeric(df[selected_param], errors='coerce')
filtered_df[selected_param] = pd.to_numeric(filtered_df[selected_param], errors='coerce')

# --- Multi-Pane Setup ---
st.sidebar.markdown("---")
st.sidebar.header("📑 Comparison Panes")
num_panes = st.sidebar.number_input("Number of Comparison Panes", min_value=1, max_value=5, value=1)

# --- Y-Axis Scaling Controls ---
st.sidebar.subheader("📈 Y-Axis Scaling")
use_manual_range = st.sidebar.checkbox("Use Manual Range", value=False)

# Calculate global range for default values
global_min = float(df[selected_param].min()) if not df[selected_param].isna().all() else 0.0
global_max = float(df[selected_param].max()) if not df[selected_param].isna().all() else 10.0

if use_manual_range:
    manual_ymin = st.sidebar.number_input("Min Y Value", value=global_min)
    manual_ymax = st.sidebar.number_input("Max Y Value", value=global_max)
else:
    st.sidebar.info(f"Using Global Range: [{global_min:.2f}, {global_max:.2f}]")


# --- Map Pane ---
st.subheader("📍 Station Lookup Map")
st.markdown("Hover over points to see IDs. Red points are selected in ANY pane.")

if 'latitude' in filtered_df.columns and 'longitude' in filtered_df.columns:
    # Collect all selected stations from session state to highlight them in red
    all_selected_stations = set()
    for i in range(num_panes):
        pane_key = f"stations_pane_{i+1}"
        if pane_key in st.session_state:
            all_selected_stations.update(st.session_state[pane_key])
    
    # Get unique stations for the map
    map_df = filtered_df.dropna(subset=['latitude', 'longitude', 'zettaicode'])
    map_df = map_df.groupby('zettaicode').first().reset_index()
    map_df['zettaicode_str'] = map_df['zettaicode'].astype(str)
    
    # Set color based on selection
    map_df['Status'] = map_df['zettaicode_str'].apply(lambda x: 'Selected' if x in all_selected_stations else 'Available')
    
    fig_map = px.scatter_mapbox(map_df, 
                                lat="latitude", 
                                lon="longitude", 
                                hover_name="zettaicode_str", 
                                hover_data={"watermass_name": True, "division": True, "zettaicode_str": False, "Status": False},
                                color="Status",
                                color_discrete_map={'Selected': 'red', 'Available': 'blue'},
                                zoom=6, 
                                height=400)
    fig_map.update_layout(mapbox_style="carto-positron")
    fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.info("Latitude and Longitude columns not found, cannot display map.")


# --- Render Comparison Panes ---
st.markdown("---")

# Pre-calculate station options for the multiselects
station_options = sorted([str(x) for x in filtered_df['zettaicode'].dropna().unique()])

for i in range(num_panes):
    pane_id = i + 1
    with st.container():
        st.header(f"Pane {pane_id}")
        
        # Determine default value for this pane's multiselect
        if f"stations_pane_{pane_id}" in st.session_state:
            p_default = st.session_state[f"stations_pane_{pane_id}"]
        else:
            p_default = station_options[i:i+1] if i < len(station_options) else None

        # Station selection for this specific pane
        selected_stations = st.multiselect(
            f"Select Station(s) for Pane {pane_id}", 
            options=station_options, 
            default=p_default,
            key=f"stations_pane_{pane_id}"
        )
        
        # Apply filters for this specific pane
        pane_df = filtered_df[
            (filtered_df['zettaicode'].astype(str).isin(selected_stations)) & 
            (filtered_df['saisuipoin'] == selected_layer) &
            (filtered_df['year'] >= selected_year_range[0]) &
            (filtered_df['year'] <= selected_year_range[1])
        ].copy()

        if selected_season != "All":
            pane_df = pane_df[pane_df['season'] == selected_season]

        if pane_df.empty or not selected_stations:
            st.warning(f"No data available for Pane {pane_id} with current filters.")
        else:
            pane_df = pane_df.sort_values('date')
            pane_df['zettaicode_str'] = pane_df['zettaicode'].astype(str)
            
            if pane_df[selected_param].isna().all():
                 st.warning(f"All values for {selected_param.upper()} are missing in Pane {pane_id}.")
            else:
                # Create interactive Plotly figure
                fig = px.line(pane_df, x='date', y=selected_param, color='zettaicode_str', markers=True,
                              title=f"Pane {pane_id} | Layer: {selected_layer} | {selected_year_range[0]}-{selected_year_range[1]}",
                              labels={selected_param: selected_param.upper(), 'date': 'Date', 'zettaicode_str': 'Station ID'},
                              template="plotly_white")
                
                fig.update_traces(line=dict(width=2), marker=dict(size=6))
                fig.update_layout(hovermode="x unified")
                
                # Apply Y-Axis range
                if use_manual_range:
                    fig.update_yaxes(range=[manual_ymin, manual_ymax])
                else:
                    if pd.notna(global_min) and pd.notna(global_max):
                        if global_max > global_min:
                            padding = (global_max - global_min) * 0.05
                            fig.update_yaxes(range=[global_min - padding, global_max + padding])
                
                st.plotly_chart(fig, use_container_width=True)
                
                with st.expander(f"Show Raw Data (Pane {pane_id})"):
                    cols_to_show = ['date', 'surveyyear', 'surveymont', 'season', 'zettaicode_str', 'saisuipoin', selected_param]
                    st.dataframe(pane_df[[c for c in cols_to_show if c in pane_df.columns]].dropna(subset=[selected_param]))
        
        st.markdown("---")
