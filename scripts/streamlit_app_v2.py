import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# Set page config
st.set_page_config(page_title="SIS Analysis Dashboard", layout="wide")

st.title("🌊 Seto Inland Sea — Analysis Dashboard")

# ---------------------------------------------------------------------------
# Layer code mapping (saisuipoin → directory name)
# ---------------------------------------------------------------------------
LAYER_MAP = {1: "surface", 2: "bottom"}

# ---------------------------------------------------------------------------
# Data Loading Helpers
# ---------------------------------------------------------------------------

@st.cache_data
def load_data():
    """Load the primary merged dataset (Tier 1)."""
    df = pd.read_feather("data/processed/merged_gdf.feather")

    # Create a proper datetime column
    if 'survey_ym' in df.columns:
        df['date'] = pd.to_datetime(df['survey_ym'], format='%Y%m', errors='coerce')
    else:
        df['date'] = pd.to_datetime(
            df[['surveyyear', 'surveymont']].assign(DAY=1).rename(
                columns={'surveyyear': 'year', 'surveymont': 'month'}
            )
        )

    # Ensure latitude and longitude are float
    if 'latitude' in df.columns:
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

    # Ensure year column is numeric
    if 'year' in df.columns:
        df['year'] = pd.to_numeric(df['year'], errors='coerce')

    return df


@st.cache_data
def load_seasonal_results(season: str, layer: str) -> dict:
    """Load pre-computed pipeline results for a season/layer combo (Tier 2)."""
    try:
        from scripts.paths import ProjectPaths
    except ImportError:
        from paths import ProjectPaths

    subset_dir = ProjectPaths.get_subset_dir(season, layer)

    results = {}
    file_map = {
        'pca_scores':       'pca_scores.csv',
        'pca_loadings':     'pca_loadings.csv',
        'pca_variance':     'pca_variance.csv',
        'env_corr_pc1':     'pca_env_corr_pc1.csv',
        'env_corr_pc2':     'pca_env_corr_pc2.csv',
        'decorrelation':    'stations_decorrelation_scale.csv',
        'interpolated_do':  'interpolated_do_df.csv',
        'yearly_do':        'yearly_do_df.csv',
    }
    for key, filename in file_map.items():
        path = subset_dir / filename
        if path.exists():
            results[key] = pd.read_csv(path, index_col=0)

    return results


@st.cache_data
def get_station_coords(df):
    """Extract unique station coordinates from the main dataset."""
    stations = df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').copy()
    stations['zettaicode'] = stations['zettaicode'].astype(str).str.zfill(8)
    return stations.set_index('zettaicode')


# ---------------------------------------------------------------------------
# Load primary data
# ---------------------------------------------------------------------------
with st.spinner("Loading dataset... This may take a few seconds on first load."):
    df = load_data()

station_coords = get_station_coords(df)

# --- Initialize Defaults for first run ---
if 'stations_pane_1' not in st.session_state:
    st.session_state['stations_pane_1'] = ['00040636', '00040632', '00040620', '00040617']

# ---------------------------------------------------------------------------
# Sidebar — Global Filters
# ---------------------------------------------------------------------------
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

# 6. Select Parameter (expanded with 01b columns)
all_params = [
    'temp', 'color', 'clearness', 'wtemp', 'ph', 'ph2', 'do_', 'do_2',
    'salt', 'salt2', 'cod', 'cod2', 'rcod', 'rcod2', 'nh4n', 'nh4n2',
    'no2n', 'no2n2', 'no3n', 'no3n2', 'tn', 'tn2', 'po4p', 'po4p2',
    'tp', 'tp2', 'chlorophyl', 'chloroph_1', 'feiochin', 'feiochin2',
    'toc', 'toc2', 'doc', 'doc2',
    'density', 'stratification', 'stratification_gradient',
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

# --- Derive season/layer strings for Tier 2 loading ---
season_for_subset = selected_season if selected_season != "All" else "Summer"
layer_for_subset = LAYER_MAP.get(selected_layer, "bottom")

# ---------------------------------------------------------------------------
# Tab Layout
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Time-Series Explorer",
    "📊 PCA Results",
    "🗺️ Spatial Analysis",
    "🔗 Environmental Correlations",
])

# =========================================================================
# TAB 1 — Time-Series Explorer (existing functionality)
# =========================================================================
with tab1:
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


# =========================================================================
# TAB 2 — PCA Results
# =========================================================================
with tab2:
    st.header(f"📊 PCA Results — {season_for_subset} {layer_for_subset.title()}")

    seasonal = load_seasonal_results(season_for_subset, layer_for_subset)

    if 'pca_variance' not in seasonal or 'pca_scores' not in seasonal:
        st.info(f"⚠️ Pipeline results not available for **{season_for_subset} {layer_for_subset}**. "
                f"Run `dvc repro` to generate PCA outputs for this subset.")
    else:
        # --- PC Selector ---
        pca_scores = seasonal['pca_scores']
        available_pcs = [c for c in pca_scores.columns if c.startswith('PC')]
        selected_pc = st.selectbox("Select Principal Component", options=available_pcs[:10], index=0, key="pca_pc_select")

        col_a, col_b = st.columns(2)

        # --- Panel 1: Scree Plot ---
        with col_a:
            st.subheader("Explained Variance (Scree Plot)")
            pca_var = seasonal['pca_variance']
            fig_scree = go.Figure()
            fig_scree.add_trace(go.Bar(
                x=pca_var['PC'] if 'PC' in pca_var.columns else pca_var.index,
                y=pca_var['Explained_Variance'],
                name='Individual',
                marker_color='steelblue',
            ))
            fig_scree.add_trace(go.Scatter(
                x=pca_var['PC'] if 'PC' in pca_var.columns else pca_var.index,
                y=pca_var['Cumulative_Variance'],
                name='Cumulative',
                mode='lines+markers',
                marker_color='coral',
            ))
            fig_scree.add_hline(y=0.8, line_dash="dash", line_color="gray", annotation_text="80%")
            fig_scree.add_hline(y=0.9, line_dash="dash", line_color="lightgray", annotation_text="90%")
            fig_scree.update_layout(
                template="plotly_white",
                height=400,
                yaxis_title="Variance Ratio",
                xaxis_title="Principal Component",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig_scree, use_container_width=True)

        # --- Panel 2: PC Score Time-Series ---
        with col_b:
            st.subheader(f"{selected_pc} Scores over Time")
            years = pca_scores.index.astype(int)
            scores = pca_scores[selected_pc]
            fig_scores = go.Figure()
            fig_scores.add_trace(go.Scatter(
                x=years, y=scores,
                mode='lines+markers',
                marker=dict(size=8, color='steelblue'),
                line=dict(width=2),
                name=selected_pc,
            ))
            fig_scores.add_hline(y=0, line_dash="dot", line_color="gray")
            fig_scores.update_layout(
                template="plotly_white",
                height=400,
                xaxis_title="Year",
                yaxis_title=f"{selected_pc} Score",
            )
            st.plotly_chart(fig_scores, use_container_width=True)

        # --- Panel 3: Station Loadings Map ---
        if 'pca_loadings' in seasonal:
            st.subheader(f"{selected_pc} — Station Eigenvector Map")
            loadings = seasonal['pca_loadings'].copy()
            loading_col = f"{selected_pc}_Loading"

            if loading_col in loadings.columns:
                # Ensure zettaicode is padded
                if 'zettaicode' in loadings.columns:
                    loadings['zettaicode'] = loadings['zettaicode'].astype(str).str.zfill(8)
                    loadings = loadings.set_index('zettaicode')

                loadings.index = loadings.index.astype(str).str.zfill(8)
                plot_data = loadings[[loading_col]].join(station_coords, how='inner').dropna()

                if not plot_data.empty:
                    fig_loadings = px.scatter_mapbox(
                        plot_data.rename_axis("zettaicode").reset_index(),
                        lat="latitude", lon="longitude",
                        color=loading_col,
                        color_continuous_scale="RdBu_r",
                        color_continuous_midpoint=0,
                        hover_name="zettaicode",
                        hover_data={loading_col: ':.4f'},
                        zoom=6, height=500,
                        title=f"{selected_pc} Loadings by Station",
                    )
                    fig_loadings.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":40,"l":0,"b":0})
                    st.plotly_chart(fig_loadings, use_container_width=True)
                else:
                    st.warning("No matching station coordinates found for loadings data.")
            else:
                st.warning(f"Column '{loading_col}' not found in loadings file.")


# =========================================================================
# TAB 3 — Spatial Analysis
# =========================================================================
with tab3:
    st.header(f"🗺️ Spatial Analysis — {season_for_subset} {layer_for_subset.title()}")

    seasonal = load_seasonal_results(season_for_subset, layer_for_subset)

    col_left, col_right = st.columns(2)

    # --- Panel 1: Decorrelation Scale Map ---
    with col_left:
        st.subheader("Decorrelation Scale Map")

        if 'decorrelation' not in seasonal:
            st.info(f"⚠️ Decorrelation results not available for **{season_for_subset} {layer_for_subset}**.")
        else:
            decorr = seasonal['decorrelation'].copy()
            # Index is Station_ID already from CSV; ensure padding
            decorr.index = decorr.index.astype(str).str.zfill(8)
            decorr_plot = decorr.join(station_coords, how='inner').dropna(subset=['Decorrelation_Scale_km', 'latitude', 'longitude'])

            if not decorr_plot.empty:
                # Following notebook 31 style: color = scale, size = neighbors
                fig_decorr = px.scatter_mapbox(
                    decorr_plot.rename_axis("Station_ID").reset_index(),
                    lat="latitude", lon="longitude",
                    color="Decorrelation_Scale_km",
                    size="n_neighbors_100km",
                    color_continuous_scale="thermal",
                    range_color=[0, 40],
                    hover_name="Station_ID",
                    hover_data={"Decorrelation_Scale_km": ":.1f", "n_neighbors_100km": True},
                    zoom=6, height=550,
                    title="Decorrelation Scale (km)",
                )
                fig_decorr.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":40,"l":0,"b":0})
                st.plotly_chart(fig_decorr, use_container_width=True)
            else:
                st.warning("No matching station coordinates for decorrelation data.")

    # --- Panel 2: Interpolated DO Heatmap ---
    with col_right:
        st.subheader("Interpolated DO Map")

        if 'interpolated_do' not in seasonal:
            st.info(f"⚠️ Interpolated DO data not available for **{season_for_subset} {layer_for_subset}**.")
        else:
            interp_do = seasonal['interpolated_do'].copy()
            interp_do.index = interp_do.index.astype(str).str.zfill(8)

            # Year selector
            available_years = sorted([int(c) for c in interp_do.columns])
            selected_year_do = st.select_slider("Select Year", options=available_years, value=available_years[-1], key="interp_year")

            year_col = str(selected_year_do)
            do_for_year = interp_do[[year_col]].rename(columns={year_col: 'DO'})
            do_plot = do_for_year.join(station_coords, how='inner').dropna()

            # Toggle raw vs interpolated
            show_raw = st.checkbox("Show raw (pre-interpolation) data instead", value=False, key="show_raw_do")
            if show_raw and 'yearly_do' in seasonal:
                raw_do = seasonal['yearly_do'].copy()
                raw_do.index = raw_do.index.astype(str).str.zfill(8)
                if year_col in raw_do.columns:
                    do_for_year = raw_do[[year_col]].rename(columns={year_col: 'DO'})
                    do_plot = do_for_year.join(station_coords, how='inner').dropna()

            if not do_plot.empty:
                fig_do = px.scatter_mapbox(
                    do_plot.rename_axis("zettaicode").reset_index(),
                    lat="latitude", lon="longitude",
                    color="DO",
                    color_continuous_scale="RdBu",
                    color_continuous_midpoint=do_plot['DO'].median(),
                    hover_name="zettaicode",
                    hover_data={"DO": ":.2f"},
                    zoom=6, height=550,
                    title=f"{'Raw' if show_raw else 'Interpolated'} DO — {selected_year_do}",
                )
                fig_do.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":40,"l":0,"b":0})
                st.plotly_chart(fig_do, use_container_width=True)
            else:
                st.warning(f"No data available for year {selected_year_do}.")


# =========================================================================
# TAB 4 — Environmental Correlations
# =========================================================================
with tab4:
    st.header(f"🔗 Environmental Correlations — {season_for_subset} {layer_for_subset.title()}")

    seasonal = load_seasonal_results(season_for_subset, layer_for_subset)

    has_pc1 = 'env_corr_pc1' in seasonal
    has_pc2 = 'env_corr_pc2' in seasonal

    if not has_pc1 and not has_pc2:
        st.info(f"⚠️ Environmental correlation results not available for **{season_for_subset} {layer_for_subset}**. "
                f"Run the pipeline (`dvc repro`) to generate them.")
    else:
        # --- Controls ---
        ctrl_col1, ctrl_col2 = st.columns(2)

        with ctrl_col1:
            pc_options = []
            if has_pc1: pc_options.append("PC1")
            if has_pc2: pc_options.append("PC2")
            selected_corr_pc = st.radio("Select PC", pc_options, horizontal=True, key="corr_pc")

        corr_df = seasonal['env_corr_pc1'] if selected_corr_pc == "PC1" else seasonal['env_corr_pc2']
        corr_df = corr_df.copy()
        corr_df.index = corr_df.index.astype(str).str.zfill(8)

        # Identify parameter columns (those with a matching _pval column)
        env_params = [c for c in corr_df.columns if f"{c}_pval" in corr_df.columns]

        with ctrl_col2:
            selected_env_param = st.selectbox("Select Environmental Parameter", options=env_params, key="env_param")

        p_col = f"{selected_env_param}_pval"

        # Join with station coords
        corr_plot = corr_df[[selected_env_param, p_col]].join(station_coords, how='inner').dropna()

        if corr_plot.empty:
            st.warning("No matching data for the selected parameter.")
        else:
            # Map p-value to marker size (significance)
            def pval_to_size(p):
                if p <= 0.001: return 18
                if p <= 0.01: return 12
                if p <= 0.05: return 7
                return 3

            def pval_to_stars(p):
                if p <= 0.001: return "***"
                if p <= 0.01: return "**"
                if p <= 0.05: return "*"
                return "ns"

            corr_plot['marker_size'] = corr_plot[p_col].apply(pval_to_size)
            corr_plot['significance'] = corr_plot[p_col].apply(pval_to_stars)

            # --- Correlation Map ---
            st.subheader(f"{selected_corr_pc} vs {selected_env_param.replace('_', ' ')}")
            
            fig_corr = px.scatter_mapbox(
                corr_plot.rename_axis("zettaicode").reset_index(),
                lat="latitude", lon="longitude",
                color=selected_env_param,
                size="marker_size",
                color_continuous_scale="PRGn",
                range_color=[-1, 1],
                hover_name="zettaicode",
                hover_data={
                    selected_env_param: ":.3f",
                    p_col: ":.4f",
                    "significance": True,
                    "marker_size": False,
                },
                zoom=6, height=550,
                title=f"{selected_corr_pc} vs {selected_env_param.replace('_', ' ')} — Correlation Map",
            )
            fig_corr.update_layout(
                mapbox_style="carto-positron",
                margin={"r":0,"t":40,"l":0,"b":0},
                coloraxis_colorbar=dict(title="Pearson r"),
            )
            st.plotly_chart(fig_corr, use_container_width=True)

            # --- Summary Boxplot ---
            st.subheader("Correlation Distribution Across Stations")

            fig_box = go.Figure()
            fig_box.add_trace(go.Box(
                y=corr_plot[selected_env_param],
                name=selected_env_param.replace('_', ' '),
                boxpoints='all',
                jitter=0.3,
                pointpos=-1.8,
                marker=dict(size=4, color='steelblue'),
                line=dict(color='steelblue'),
            ))
            fig_box.add_hline(y=0, line_dash="dot", line_color="gray")
            fig_box.update_layout(
                template="plotly_white",
                height=350,
                yaxis_title="Pearson Correlation (r)",
                showlegend=False,
            )
            st.plotly_chart(fig_box, use_container_width=True)

            # --- Significance breakdown ---
            sig_counts = corr_plot['significance'].value_counts()
            st.caption(
                f"Significance breakdown: "
                + " | ".join([f"**{k}**: {v} stations" for k, v in sig_counts.items()])
            )
