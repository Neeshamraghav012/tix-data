import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go

# --- Streamlit Page Config ---
st.set_page_config(page_title="🎟️ Tickoo Dashboard", layout="wide")


# --- Title and Description ---
st.title("🎟️ Tickoo Analytics Dashboard")
st.markdown("""
Welcome to **Tickoo**, your smart ticket analytics dashboard!  
Upload your CSV file below to explore sales insights, price trends, and section-wise analytics — all interactively.
""")

# File uploader
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file:
    # Read the uploaded file
    df = pd.read_csv(uploaded_file)

    # Convert 'Qty' and 'Price' to numeric
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce')
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')

    # Remove rows where Qty or Price is zero or NaN
    # df = df[(df['Qty'] > 0) & (df['Price'].notna())]

    # --- Remove Outliers from Price only ---
    Q1 = df['Price'].quantile(0.25)
    Q3 = df['Price'].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    df = df[(df['Price'] >= lower_bound) & (df['Price'] <= upper_bound)]

    # --- 🔍 Search and Filter Section ---
    st.subheader("🔍 Search & Filter Data")

    # Convert date column if present
    if 'Date/Time (EDT)' in df.columns:
        df['Date/Time (EDT)'] = pd.to_datetime(df['Date/Time (EDT)'], errors='coerce')
        df['Date'] = df['Date/Time (EDT)'].dt.date

    col1, col2, col3 = st.columns(3)

    # Date filter
    unique_dates = sorted(df['Date'].dropna().unique())
    selected_date = col1.selectbox("Select Date", ["All"] + list(map(str, unique_dates)))

    # Section filter
    unique_sections = sorted(df['Section'].dropna().unique())
    selected_section = col2.selectbox("Select Section", ["All"] + list(unique_sections))

    # Zone filter
    if 'Zone' in df.columns:
        unique_zones = sorted(df['Zone'].dropna().unique())
        selected_zone = col3.selectbox("Select Zone", ["All"] + list(unique_zones))
    else:
        selected_zone = "All"

    # Apply filters
    filtered_df = df.copy()
    if selected_date != "All":
        filtered_df = filtered_df[filtered_df['Date'].astype(str) == selected_date]
    if selected_section != "All":
        filtered_df = filtered_df[filtered_df['Section'] == selected_section]
    if selected_zone != "All":
        filtered_df = filtered_df[filtered_df['Zone'] == selected_zone]

    # Show number of rows in filtered data
    st.markdown(f"**Number of rows in filtered data:** {len(filtered_df):,}")

    # Show filtered data
    st.subheader("🧾 Filtered Data Preview")
    st.dataframe(filtered_df, use_container_width=True)

    # Use filtered data for the rest of the dashboard
    df = filtered_df

    # --- KPIs Section ---
    st.markdown("## 📊 Key Performance Indicators")
    col1, col2, col3 = st.columns(3)

    total_tickets = int(df['Qty'].sum())
    avg_price = round(df['Price'].mean(), 2)
    highest_price = round(df['Price'].max(), 2)

    with col1:
        st.metric("🎫 Total Tickets Sold", f"{total_tickets:,}")
    with col2:
        st.metric("💰 Average Ticket Price", f"${avg_price:,.0f}")
    with col3:
        st.metric("🏆 Highest Ticket Price", f"${highest_price:,.0f}")

    # Add visual gap
    st.markdown("<br><hr style='border: 1px solid #ddd;'><br>", unsafe_allow_html=True)

    # --- Min and Max Prices Section ---
    st.markdown("## 💰 Min and Max Prices Per Section")

    price_stats = df.groupby('Section')['Price'].agg(['min', 'max']).reset_index()
    price_stats.columns = ['Section', 'Min Price', 'Max Price']

    styled_price_stats = (
        price_stats.style
        .format({
            "Min Price": "${:.0f}",
            "Max Price": "${:.0f}"
        })
        .background_gradient(subset=["Max Price"], cmap="Blues")
        .set_properties(**{
            'text-align': 'center',
            'font-weight': 'bold',
        })
    )

    st.dataframe(styled_price_stats, use_container_width=True)


    # Set Seaborn and Matplotlib styles
    sns.set_style("darkgrid")
    plt.style.use("dark_background")

    # Filter top sections by ticket count
    top_sections = df['Section'].value_counts().nlargest(10).index  # Top 10 sections
    df_top = df[df['Section'].isin(top_sections)]

    # Plot 1: Number of tickets sold per section
    st.write("## Number of Tickets Sold Per Section")
    fig1, ax1 = plt.subplots(figsize=(16, 6))
    sns.countplot(x="Section", data=df_top, ax=ax1, order=top_sections)
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=45, ha='right')
    st.pyplot(fig1)

    # Plot 2: Price variation according to top sections
    st.write("## Price Variation According to Top Sections")
    fig2, ax2 = plt.subplots(figsize=(16, 6))
    sns.scatterplot(x="Section", y="Price", data=df_top, ax=ax2, palette="coolwarm", s=100)
    ax2.set_title("Price Variation for Top Sections")
    ax2.set_xticklabels(ax2.get_xticklabels(), rotation=45, ha='right')
    st.pyplot(fig2)

    # Plot 3: Price variation per section (Violin Plot)
    st.write("## Price Variation Per Section (Violin Plot)")
    fig3, ax3 = plt.subplots(figsize=(16, 6))
    sns.violinplot(x="Section", y="Price", data=df_top, ax=ax3, palette="coolwarm")
    ax3.set_xticklabels(ax3.get_xticklabels(), rotation=45, ha='right')
    ax3.set_title("Price Distribution Per Section")
    st.pyplot(fig3)

    df['Date/Time (EDT)'] = pd.to_datetime(df['Date/Time (EDT)'])
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
    df = df.dropna(subset=['Price', 'Date/Time (EDT)'])
    df = df.sort_values(by='Date/Time (EDT)')

    # Plot: Number of Tickets Sold Over Time (Grouped by Date)
    st.write("## Number of Tickets Sold Per Day")
    df['Date'] = df['Date/Time (EDT)'].dt.date
    tickets_per_day = df.groupby('Date')['Qty'].sum().reset_index()

    fig, ax = plt.subplots(figsize=(14, 5))
    sns.lineplot(data=tickets_per_day, x='Date', y='Qty', marker='o', ax=ax)
    ax.set_title("Number of Tickets Sold Per Day")
    ax.set_xlabel("Date")
    ax.set_ylabel("Tickets Sold")
    plt.xticks(rotation=45)
    st.pyplot(fig)

    # Plot 5: Average Price Over Time (with smoothing)
    st.write("## Average Price Over Time")
    df['Smoothed_Price'] = df['Price'].rolling(window=5).mean()
    fig5, ax5 = plt.subplots(figsize=(12, 6))
    sns.lineplot(x="Date/Time (EDT)", y="Smoothed_Price", data=df, ax=ax5)
    plt.xticks(rotation=45)
    st.pyplot(fig5)

    # Plot: Separate Time Series of Price Over Time for Each Zone
    st.write("## Price Over Time for Each Zone")
    if 'Zone' in df.columns:
        import itertools
        color_list = sns.color_palette("Set2", n_colors=10)
        color_cycle = itertools.cycle(color_list)
        top_zones = df['Zone'].value_counts().nlargest(5).index
        df_zone_time = df[df['Zone'].isin(top_zones)]

        for zone in top_zones:
            st.write(f"### Zone: {zone}")
            zone_df = df_zone_time[df_zone_time['Zone'] == zone]
            fig, ax = plt.subplots(figsize=(14, 5))
            color = next(color_cycle)
            sns.lineplot(data=zone_df, x='Date/Time (EDT)', y='Price', ax=ax, color=color)
            ax.set_title(f"Price Over Time - {zone}")
            plt.xticks(rotation=45)
            st.pyplot(fig)
    else:
        st.warning("Zone column not found in the uploaded data.")

    # Plot 6: Ticket Quantity distribution
    st.write("## Ticket Quantity Distribution")
    fig6, ax6 = plt.subplots(figsize=(12, 6))
    sns.countplot(x="Qty", data=df, ax=ax6)
    st.pyplot(fig6)
