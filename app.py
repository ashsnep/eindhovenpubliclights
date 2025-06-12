import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap
import plotly.express as px
from datetime import datetime

# Load and preprocess the data
@st.cache_data
def load_data():
    df = pd.read_csv("public_lights_Eindhoven.csv", delimiter=";")
    df["DATE_PLACEMENT"] = pd.to_datetime(df["DATE_PLACEMENT"], errors='coerce')
    df["DATE_MAINTENENCE"] = pd.to_datetime(df["DATE_MAINTENENCE"], errors='coerce')
    df["lon"] = df["GEO_SHAPE"].apply(lambda x: eval(x)["coordinates"][0])
    df["lat"] = df["GEO_SHAPE"].apply(lambda x: eval(x)["coordinates"][1])
    
    # Derived columns
    today = pd.to_datetime(datetime.today())
    df["overdue_days"] = (today - df["DATE_MAINTENENCE"]).dt.days.clip(lower=0)
    df["age_days"] = (today - df["DATE_PLACEMENT"]).dt.days.clip(lower=0)
    df["priority_score"] = (
        df["overdue_days"] * 1.5 +
        df["WATTAGE"].fillna(0) * 0.05 +
        df["age_days"] * 0.01
    )
    
    return df

df = load_data()

st.title("Eindhoven Public Lights Dashboard")

# Sidebar filters
st.sidebar.header("Filters")
districts = st.sidebar.multiselect("Select District(s)", options=df["DISTRICT"].unique(), default=df["DISTRICT"].unique())
types = st.sidebar.multiselect("Select Light Type(s)", options=df["TYPE"].dropna().unique(), default=df["TYPE"].dropna().unique())
wattage_min, wattage_max = st.sidebar.slider("Wattage Range", min_value=0, max_value=int(df["WATTAGE"].max()), value=(0, int(df["WATTAGE"].max())))
maintenance_limit = st.sidebar.date_input("Maintenance Before", datetime(2026, 1, 1))

# Apply filters
filtered_df = df[
    (df["DISTRICT"].isin(districts)) &
    (df["TYPE"].isin(types)) &
    (df["WATTAGE"].between(wattage_min, wattage_max)) &
    (df["DATE_MAINTENENCE"] <= pd.to_datetime(maintenance_limit))
].copy()

filtered_df.sort_values("priority_score", ascending=False, inplace=True)

# Clustered Map with Priority
st.subheader("Map of Lights Needing Maintenance")

view_option = st.radio("Choose map view:", ["Clustered", "Non-Clustered"], horizontal=True)

map_view = folium.Map(location=[51.45, 5.48], zoom_start=13)

if view_option == "Clustered":
    marker_group = MarkerCluster().add_to(map_view)
else:
    marker_group = folium.FeatureGroup(name="Lights").add_to(map_view)

for _, row in filtered_df.iterrows():
    folium.CircleMarker(
        location=(row["lat"], row["lon"]),
        radius=5,
        color=row["COLOR"],
        fill=True,
        fill_opacity=0.7,
        popup=(f"<b>Type:</b> {row['TYPE']}<br>"
               f"<b>District:</b> {row['DISTRICT']}<br>"
               f"<b>Placement:</b> {row['DATE_PLACEMENT'].date()}<br>"
               f"<b>Maintenance:</b> {row['DATE_MAINTENENCE'].date()}<br>"
               f"<b>Wattage:</b> {row['WATTAGE']}<br>"
               f"<b>Priority Score:</b> {row['priority_score']:.1f}")
    ).add_to(marker_group)

st_folium(map_view, width=700, height=500)


# Heatmap
st.subheader("ight Density Heatmap")
heatmap_map = folium.Map(location=[51.45, 5.48], zoom_start=13)
heat_data = filtered_df[["lat", "lon"]].dropna().values.tolist()
HeatMap(heat_data).add_to(heatmap_map)
st_folium(heatmap_map, width=700, height=500)

# Gantt Chart for Maintenance Schedule
st.subheader("Maintenance Gantt Chart")
gantt_df = filtered_df[["OBJECTID", "DISTRICT", "DATE_PLACEMENT", "DATE_MAINTENENCE"]].dropna()
gantt_df["Task"] = gantt_df["DISTRICT"] + " - " + gantt_df["OBJECTID"].astype(str)
fig_gantt = px.timeline(
    gantt_df,
    x_start="DATE_PLACEMENT",
    x_end="DATE_MAINTENENCE",
    y="Task",
    title="Light Lifecycle (Placement to Maintenance)",
    color="DISTRICT"
)
fig_gantt.update_yaxes(autorange="reversed")
st.plotly_chart(fig_gantt, use_container_width=True)

# Timeline Animation of Placement
st.subheader("Timeline Animation of Light Placement")
timeline_df = filtered_df.copy()
timeline_df["year"] = timeline_df["DATE_PLACEMENT"].dt.year
fig_timeline = px.scatter_geo(
    timeline_df,
    lat="lat",
    lon="lon",
    color="TYPE",
    size="WATTAGE",
    animation_frame="year",
    projection="natural earth",
    title="Public Light Placement Over Time"
)
st.plotly_chart(fig_timeline, use_container_width=True)

# Light Type Distribution
st.subheader("Light Type Distribution")
type_counts = filtered_df["TYPE"].value_counts().reset_index()
type_counts.columns = ["Type", "Count"]
fig_type = px.bar(
    type_counts,
    x="Type",
    y="Count",
    color="Type",
    title="Distribution of Light Types",
    text="Count"
)
st.plotly_chart(fig_type, use_container_width=True)

# Final Maintenance Table
st.subheader("Prioritized Maintenance Table")
st.dataframe(filtered_df[[
    "OBJECTID", "DISTRICT", "NEIGHBORHOOD", "DATE_PLACEMENT",
    "DATE_MAINTENENCE", "TYPE", "COLOR", "WATTAGE", "priority_score"
]])
