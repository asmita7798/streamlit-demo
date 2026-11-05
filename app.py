"""Weather dashboard. Run: python -m streamlit run app.py"""

import hashlib
import io
import random

import pandas as pd
import plotly.express as px
import streamlit as st


# 1. PAGE
st.set_page_config(page_title="Weather Explorer", layout="wide")
st.title("Weather Explorer")

MEASUREMENTS = ["precipitation", "temp_max", "temp_min", "wind"]


# 2. DATA
@st.cache_data
def example_data():
    rng = random.Random(42)
    dates = pd.date_range("2025-01-01", periods=30)

    return pd.DataFrame([
        {
            "date": date,
            "location": location,
            "precipitation": round(rng.uniform(0, 10), 1),
            "temp_max": round(rng.uniform(18, 28), 1),
            "temp_min": round(rng.uniform(8, 17), 1),
            "wind": round(rng.uniform(0, 8), 1),
        }
        for location in ["New York", "Seattle"]
        for date in dates
    ])


@st.cache_data
def read_csv(file_bytes):
    return pd.read_csv(io.BytesIO(file_bytes))


uploaded = st.sidebar.file_uploader("Upload a weather CSV", type="csv")

with st.spinner("Loading data..."):
    try:
        file_bytes = uploaded.getvalue() if uploaded is not None else None
        df = read_csv(file_bytes) if file_bytes is not None else example_data()

        required = ["date", "location", *MEASUREMENTS]
        missing = [column for column in required if column not in df.columns]

        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}")

        if df.empty:
            raise ValueError("The CSV must contain at least one data row.")

    except (ValueError, UnicodeDecodeError) as error:
        st.error(f"Could not load the data: {error}")
        st.stop()

st.caption(
    f"Uploaded file: {uploaded.name}"
    if uploaded is not None
    else "Fictional weather data for demonstration—not actual city measurements."
)

dataset_key = (
    hashlib.sha256(file_bytes).hexdigest()
    if file_bytes is not None
    else "example"
)

# Keep original values for the table and download.
plot_data = df.copy()
plot_data["date"] = pd.to_datetime(
    plot_data["date"], errors="coerce", format="mixed", utc=True
)

if not plot_data["date"].notna().any():
    st.error("The date column contains no valid dates.")
    st.stop()


# 3. CONTROLS
measurement = st.sidebar.selectbox(
    "Measurement",
    MEASUREMENTS,
    key=f"measurement_{dataset_key}",
)

locations = sorted(df["location"].dropna().astype(str).unique())

selected_locations = st.sidebar.multiselect(
    "Location",
    locations,
    default=locations,
    key=f"locations_{dataset_key}",
)

first_date = plot_data["date"].min().date()
last_date = plot_data["date"].max().date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(first_date, last_date),
    min_value=first_date,
    max_value=last_date,
    key=f"date_range_{dataset_key}",
)

if len(date_range) != 2:
    st.info("Choose a start and end date.")
    st.stop()


# 4. FILTERING
plot_data = plot_data[
    plot_data["location"].astype(str).isin(selected_locations)
    & plot_data["date"].dt.date.between(*date_range)
].copy()

filtered = df.loc[plot_data.index]

if filtered.empty:
    st.warning("Choose at least one location and a date range containing data.")
    st.stop()


# 5. LAYOUT
left, right = st.columns(2)
left.metric("Selected rows", len(filtered))
right.metric("Selected locations", filtered["location"].nunique())

data_tab, chart_tab = st.tabs(["Data", "Chart"])

with data_tab:
    st.subheader("Selected data")
    st.dataframe(filtered, hide_index=True, width="stretch")

    with st.expander("Summary statistics"):
        numeric_data = filtered[MEASUREMENTS].apply(
            pd.to_numeric, errors="coerce"
        )
        numeric_data = numeric_data.replace(
            [float("inf"), float("-inf")], float("nan")
        )
        st.dataframe(numeric_data.describe())


# 6. CHART
with chart_tab:
    st.subheader(f"{measurement} over time")

    plot_data[measurement] = pd.to_numeric(
        plot_data[measurement], errors="coerce"
    )
    plot_data[measurement] = plot_data[measurement].replace(
        [float("inf"), float("-inf")], float("nan")
    )

    chart_data = plot_data.dropna(subset=["date", measurement])
    skipped = len(plot_data) - len(chart_data)

    if skipped:
        st.caption(f"Skipped {skipped} rows with invalid measurement values.")

    if chart_data.empty:
        st.warning("No valid measurements are available for this selection.")
    else:
        chart_data = chart_data.sort_values(["location", "date"])

        figure = px.line(
            chart_data,
            x="date",
            y=measurement,
            color="location",
            render_mode="svg",
            labels={"date": "Date", "location": "Location"},
            color_discrete_map={
                "New York": "#0072B2",
                "Seattle": "#D55E00",
            },
        )

        st.plotly_chart(figure, width="stretch")


# 7. EXPORT
st.download_button(
    "Download selected data",
    data=filtered.to_csv(index=False),
    file_name="weather_selection.csv",
    mime="text/csv",
)
