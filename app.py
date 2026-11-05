"""Cmd to run this script: streamlit run app.py"""
# Imports
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st


## Page setup
st.set_page_config(page_title="Weather Explorer", layout="wide")

st.html("""
<style>
[data-testid="stMainBlockContainer"] {
    padding-top: 2rem !important;
}
</style>
""")

st.title("Weather Explorer")


## Data loading
@st.cache_data
def load_data():
    path = Path(__file__).with_name("weather.csv")
    return pd.read_csv(path, parse_dates=["date"])


df = load_data() #loads the data in a dataframe

# setting consistent colours for the cities
colors = {
    "New York": "#0072B2",
    "Seattle": "#D55E00",
}


## Input widgets (on sidebar)
locations = sorted(df["location"].unique())

# creates multi-select list
selected_locations = st.sidebar.multiselect(
    "Location",
    locations,
    default=locations,
)

first_date = df["date"].min().date()
last_date = df["date"].max().date()

# creates date range selector
date_range = st.sidebar.date_input(
    "Date range",
    value=(first_date, last_date),
    min_value=first_date,
    max_value=last_date,
)
if len(date_range) != 2:
    st.info("Choose a start and end date.")
    st.stop()
start_date, end_date = date_range


# Data filtering
filtered = df[
    df["location"].isin(selected_locations)
    & df["date"].dt.date.between(start_date, end_date)
].sort_values("date")

if filtered.empty:
    st.warning("Select a location and a date range containing data.")
    st.stop()


## Overview
st.subheader("Overview")
st.caption(
    f"{start_date:%d %b %Y} – {end_date:%d %b %Y} · "
    f"{', '.join(selected_locations)} · "
    f"{len(filtered):,} daily records"
)

common_weather = ", ".join(filtered["weather"].mode())

high, rain, wind, weather = st.columns(4) # creates 4 equal width layout containers for displaying overview metrics on dashboard

high.metric("Avg. daily high", f"{filtered['temp_max'].mean():.1f} °C")
rain.metric("Avg. precipitation", f"{filtered['precipitation'].mean():.1f} mm/day")
wind.metric("Avg. wind speed", f"{filtered['wind'].mean():.1f} m/s")
weather.metric("Most common weather", common_weather)


## Charts
# Line chart: temperature over time
line_chart = px.line(
    filtered,
    x="date",
    y="temp_max",
    color="location",
    title="Daily maximum temperature",
    labels={
        "date": "Date",
        "temp_max": "Temperature (°C)",
    },
    color_discrete_map=colors,
    render_mode="svg",
)


# Scatter plot: wind and precipitation
scatter_chart = px.scatter(
    filtered,
    x="wind",
    y="precipitation",
    color="location",
    title="Wind and precipitation",
    labels={
        "wind": "Wind speed (m/s)",
        "precipitation": "Precipitation (mm)",
    },
    hover_data=["date", "weather"],
    color_discrete_map=colors,
    render_mode="svg",
)


# Bar chart: days per weather condition and location
weather_counts = (
    filtered.groupby(["weather", "location"])
    .size()
    .reset_index(name="Days")
)
bar_chart = px.bar(
    weather_counts,
    x="weather",
    y="Days",
    color="location",
    barmode="group",
    title="Weather conditions",
    labels={"weather": "Weather"},
    color_discrete_map=colors,
)


# Chart layout 
for chart in [line_chart, scatter_chart, bar_chart]:
    chart.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=80, b=40),
        legend=dict(orientation="h", y=1.12, x=0),
        legend_title_text="",
    )

# creates equal spaced containers to hold the charts
left, middle, right = st.columns(3)

# displays charts on the dashboard
left.plotly_chart(line_chart, width="stretch")
middle.plotly_chart(scatter_chart, width="stretch")
right.plotly_chart(bar_chart, width="stretch")

