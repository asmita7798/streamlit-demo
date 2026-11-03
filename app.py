"""Demo for weather dashboard. Run: python -m streamlit run app.py

The default data is fictional. Uploaded CSVs can use their own column names.
"""

import hashlib
import io
import random

import pandas as pd
import plotly.express as px
import streamlit as st


# 1. PAGE: controls and outputs appear in the order this script runs.
st.set_page_config(page_title="Weather Explorer", layout="wide")
st.title("Weather Explorer")


# 2. DATA: cache results so widget changes do not repeat the same loading work.
@st.cache_data
def example_data():
    rng = random.Random(42)
    return pd.DataFrame([
        {
            "Day": day,
            "City": city,
            "Temperature": round(rng.uniform(12, 28), 1),
            "Rainfall": round(rng.uniform(0, 10), 1),
        }
        for city in ["City A", "City B", "City C"]
        for day in range(1, 31)
    ])


@st.cache_data
def read_csv(file_bytes):
    # Uploaded files can be read by pandas without writing them to disk.
    return pd.read_csv(io.BytesIO(file_bytes))

#https://github.com/observablehq/sample-datasets/blob/main/weather.csv - sample dataset link
uploaded = st.sidebar.file_uploader(
    "Upload a CSV", type="csv",
)
with st.spinner("Loading data..."):
    try:
        file_bytes = uploaded.getvalue() if uploaded is not None else None
        df = read_csv(file_bytes) if file_bytes is not None else example_data()
        if df.empty:
            raise ValueError("The CSV must contain at least one data row.")
    except (ValueError, UnicodeDecodeError) as error:
        st.error(f"Could not load the data: {error}")
        st.stop()

st.caption(
    f"Uploaded file: {uploaded.name}" if uploaded is not None
    else "Fictional daily weather measurements — upload a CSV to explore your own data."
)


# 3. WIDGETS: their current values are ordinary Python variables.
# An interaction normally reruns the entire script with those new values.
# Different files get fresh controls, even when they have the same column names.
dataset_key = hashlib.sha256(file_bytes).hexdigest() if file_bytes is not None else "example"
columns = list(df.columns)
numeric_columns = list(df.select_dtypes(include="number").columns)
date_names = {"date", "time", "timestamp", "datetime"}
default_x = next((column for column in columns if column.lower() in date_names), columns[0])
x_column = st.sidebar.selectbox(
    "X axis", columns, index=columns.index(default_x), key=f"x_{dataset_key}",
)
y_column = None
if numeric_columns:
    default_y = "Temperature" if "Temperature" in numeric_columns else numeric_columns[0]
    y_column = st.sidebar.selectbox(
        "Y axis (numeric)", numeric_columns,
        index=numeric_columns.index(default_y), key=f"y_{dataset_key}",
    )

as_dates = st.sidebar.checkbox(
    "Treat X axis as dates", value=x_column.lower() in date_names,
    key=f"dates_{dataset_key}_{x_column}",
    help="Use for date strings such as 2012-01-01. Numeric columns are kept as numbers by default.",
)
# Convert a copy for plotting; keep the uploaded values for the table and download.
plot_data = df.copy()
if as_dates:
    plot_data[x_column] = pd.to_datetime(
        plot_data[x_column], errors="coerce", format="mixed", utc=True,
    )

group_columns = [column for column in columns if column not in numeric_columns and column != x_column]
group_options = [None, *group_columns]
default_group = next(
    (column for column in group_columns if column.lower() in {"city", "location"}), None,
)
group_column = st.sidebar.selectbox(
    "Group / colour by", group_options, index=group_options.index(default_group),
    format_func=lambda column: "No grouping" if column is None else column,
    key=f"group_{dataset_key}_{x_column}",
)
if group_column is not None:
    available_groups = sorted(df[group_column].dropna().astype(str).unique())
    groups = st.sidebar.multiselect(
        f"Values in {group_column}", available_groups, default=available_groups,
        key=f"values_{dataset_key}_{group_column}",
    )
    plot_data = plot_data[plot_data[group_column].astype(str).isin(groups)]
    plot_data[group_column] = plot_data[group_column].astype(str)

chart_type = st.sidebar.radio("Chart", ["Line", "Bar", "Scatter"], horizontal=True)
show_points = st.sidebar.checkbox("Show individual points", value=True)

if as_dates and plot_data[x_column].notna().any():
    first_date, last_date = plot_data[x_column].min().date(), plot_data[x_column].max().date()
    date_range = st.sidebar.date_input(
        "Date range", value=(first_date, last_date), min_value=first_date, max_value=last_date,
        key=f"date_range_{dataset_key}_{x_column}",
    )
    if len(date_range) != 2:
        st.info("Choose a start and end date.")
        st.stop()
    plot_data = plot_data[plot_data[x_column].dt.date.between(*date_range)]
elif not as_dates and x_column in numeric_columns:
    finite_x = plot_data[x_column].replace([float("inf"), float("-inf")], float("nan")).dropna()
    if not finite_x.empty and finite_x.min() < finite_x.max():
        low, high = float(finite_x.min()), float(finite_x.max())
        start, end = st.sidebar.slider(
            f"Range of {x_column}", low, high, (low, high),
            key=f"number_range_{dataset_key}_{x_column}",
        )
        plot_data = plot_data[plot_data[x_column].between(start, end)]

# One selection controls the table, summary values, chart and CSV download.
filtered = df.loc[plot_data.index]
if filtered.empty:
    st.warning("Choose a selection containing data.")
    st.stop()


# 4. LAYOUT: columns arrange summary values; tabs group different views.
left, right = st.columns(2)
left.metric("Selected rows", len(filtered))
right.metric("Columns", len(filtered.columns))
data_tab, chart_tab = st.tabs(["Data", "Chart"])

with data_tab:
    st.subheader("Selected data")
    st.dataframe(filtered, hide_index=True, width="stretch")
    with st.expander("Summary statistics"):
        if numeric_columns:
            st.dataframe(filtered[numeric_columns].describe())
        else:
            st.dataframe(filtered.describe().astype(str))

with chart_tab:
    if y_column is None:
        st.info("This CSV has no numeric columns. You can inspect and download the data; a chart needs a numeric Y axis.")
    else:
        st.subheader(f"{y_column} by {x_column}")
        # Missing or infinite values in other columns do not prevent plotting.
        chart_data = plot_data.replace([float("inf"), float("-inf")], float("nan"))
        chart_data = chart_data.dropna(subset=[x_column, y_column])
        skipped = len(plot_data) - len(chart_data)
        if skipped:
            st.caption(f"Skipped {skipped} rows with missing or invalid axis values in the chart.")
        if chart_data.empty:
            st.warning("No valid values for these axes. Choose other columns or change the date setting.")
        else:
            chart_data = chart_data.sort_values(x_column)
            chart_options = dict(
                data_frame=chart_data, x=x_column, y=y_column, color=group_column,
                color_discrete_sequence=["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00"],
            )
            # 5. CHARTS: Plotly builds the figure; Streamlit displays it.
            if chart_type == "Line":
                figure = px.line(**chart_options, markers=show_points, render_mode="svg")
            elif chart_type == "Bar":
                figure = px.bar(**chart_options, barmode="group")
            else:
                figure = px.scatter(**chart_options, render_mode="svg")
            st.plotly_chart(figure, width="stretch")
            st.caption("Charts show individual rows. Aggregate repeated X values first if you want totals or averages.")


# 6. EXPORT: downloads do not change the data or files used by the app.
st.download_button(
    "Download selected data",
    data=filtered.to_csv(index=False),
    file_name="selection.csv", mime="text/csv",
)
