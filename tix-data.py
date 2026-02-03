import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.express as px
from datetime import datetime
import plotly.graph_objects as go


# --- Streamlit Page Config ---
st.set_page_config(page_title="Tickoo Dashboard", layout="wide")


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

    # Original filename (without extension)
    original_filename = uploaded_file.name.replace(".csv", "")

    # Editable filename input
    edited_filename = st.text_input(
        "📝 Edit file name (used for exports & reference)",
        value=original_filename
    )

    csv_data = df.to_csv(index=False).encode("utf-8")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")


    st.download_button(
        label="⬇️ Download Filtered Data",
        data=csv_data,
        file_name=f"{edited_filename}_{timestamp}.csv",
        mime="text/csv"
    )


    # Convert 'Qty' and 'Price' to numeric
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce')
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')

    # Remove rows where Qty or Price is zero or NaN
    # df = df[(df['Qty'] > 0) & (df['Price'].notna())]

    # Replace Qty = 0 with 2
    df.loc[df['Qty'] == 0, 'Qty'] = 2

    # Remove rows where Qty is NaN or <= 0 (after replacement safety)
    df = df[df['Qty'].notna() & (df['Qty'] > 0)]

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

    # Show filtered data
    st.subheader("🧾 Filtered Data Preview")
    st.dataframe(filtered_df, use_container_width=True)

    # Use filtered data for the rest of the dashboard
    df = filtered_df

    st.markdown("## 🧾 Event Details")

    event_date = st.date_input(
        "📅 Event Date",
        value=df['Date/Time (EDT)'].dt.date.mode()[0]
        if 'Date/Time (EDT)' in df.columns else None
    )

    presale_date = st.date_input(
        "⏰ Presale Date",
        value=None,
        help="Date when presale started"
    )

    public_sale_date = st.date_input(
        "🛒 Public Sale Date",
        value=None,
        help="Date when public sale started"
    )

    tickets_available = st.number_input(
        "🎟️ Total Tickets Available",
        min_value=0,
        step=100,
        help="Total tickets released for this event"
    )

    st.session_state['event_meta'] = {
            # "event_name": event_name,
            "event_date": event_date,
            "presale_date": presale_date,
            "tickets_available": tickets_available,
            "public_sale_date": public_sale_date,
    }

    if tickets_available > 0:
        sold = df['Qty'].sum()
        sell_through = sold / tickets_available * 100

        st.metric(
            "📈 Sell-through Rate",
            f"{sell_through:.1f}%",
            help="Percentage of total inventory sold"
        )



    st.markdown("## 🚨 Market Signals")

    warnings = []

    # -------------------------
    # Demand acceleration check
    # -------------------------
    recent_sales = df[
        df['Date/Time (EDT)'] >= df['Date/Time (EDT)'].max() - pd.Timedelta(days=3)
    ]

    avg_recent = recent_sales['Qty'].sum() / 3  # Average over last 3 days
    st.markdown(f"**Average Tickets Sold in Last 3 Days:** {avg_recent:.2f}")
    total_days = df['Date'].nunique()
    avg_overall = df['Qty'].sum() / total_days if total_days > 0 else 0
    st.markdown(f"**Overall Average Tickets Sold Per Day:** {avg_overall:.2f}")

    if avg_recent > avg_overall:
        warnings.append(
            f"🔥 Demand accelerating: Last 3 days avg ({avg_recent:.2f}) "
            f"> Overall avg ({avg_overall:.2f})"
        )

    # -------------------------
    # Inventory pressure checks
    # -------------------------
    if tickets_available > 0:
        sold = df['Qty'].sum()
        remaining_ratio = (tickets_available - sold) / tickets_available

        if remaining_ratio < 0.5:
            warnings.append("⚠️ Low inventory — less than 50% remaining")

        if sold / tickets_available > 0.3:
            warnings.append("🚨 Near sell-out risk")

    if warnings:
        for w in warnings:
            st.warning(w)
    else:
        st.success("✅ Market conditions stable")





    presale_sold = 0
    general_sale_sold = 0

    if presale_date and public_sale_date:
        presale_start = pd.to_datetime(presale_date)
        public_sale_start = pd.to_datetime(public_sale_date)

        presale_sold = df[
            (df['Date/Time (EDT)'] >= presale_start) &
            (df['Date/Time (EDT)'] < public_sale_start)
        ]['Qty'].sum()

        general_sale_sold = df[
            df['Date/Time (EDT)'] >= public_sale_start
        ]['Qty'].sum()


    st.markdown("## 📊 Tickets Sold: Presale vs General Sale")

    sales_phase_df = pd.DataFrame({
        "Sale Phase": ["Presale", "General Sale"],
        "Tickets Sold": [presale_sold, general_sale_sold]
    })

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(
        data=sales_phase_df,
        x="Sale Phase",
        y="Tickets Sold",
        ax=ax
    )

    ax.set_title("Tickets Sold by Sales Phase")
    ax.set_ylabel("Tickets Sold")
    ax.set_xlabel("")

    for i, v in enumerate(sales_phase_df["Tickets Sold"]):
        ax.text(i, v, f"{int(v):,}", ha="center", va="bottom")

    st.pyplot(fig)

    total_sold = presale_sold + general_sale_sold

    col1, col2 = st.columns(2)

    col1.metric(
        "🎟️ Presale Tickets Sold",
        f"{int(presale_sold):,}",
        f"{(presale_sold / total_sold * 100):.1f}%" if total_sold > 0 else None
    )

    col2.metric(
        "🛒 General Sale Tickets Sold",
        f"{int(general_sale_sold):,}",
        f"{(general_sale_sold / total_sold * 100):.1f}%" if total_sold > 0 else None
    )


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



    # Plot: Number of Tickets Sold Over Time (Grouped by Date)
    st.write("## Number of Tickets Sold Per Day")

    # Prepare data
    df['Date'] = df['Date/Time (EDT)'].dt.date
    tickets_per_day = df.groupby('Date')['Qty'].sum().reset_index()

    # Convert Date to datetime for rolling calculations
    tickets_per_day['Date'] = pd.to_datetime(tickets_per_day['Date'])

    # ---- Metrics ----
    avg_tickets_per_day = tickets_per_day['Qty'].sum() / len(tickets_per_day) if len(tickets_per_day) > 0 else 0



    # Peak day
    peak_row = tickets_per_day.loc[tickets_per_day['Qty'].idxmax()]
    peak_date = peak_row['Date']
    peak_qty = peak_row['Qty']

    # ---- Plot ----
    fig, ax = plt.subplots(figsize=(14, 5))

    # Daily tickets sold
    sns.lineplot(
        data=tickets_per_day,
        x='Date',
        y='Qty',
        marker='o',
        ax=ax,
        label='Tickets Sold Per Day'
    )

    # Average line
    ax.axhline(
        avg_tickets_per_day,
        color='red',
        linestyle='--',
        linewidth=2,
        label=f'Average ({avg_tickets_per_day:.2f})'
    )

    # Peak day highlight
    ax.scatter(
        peak_date,
        peak_qty,
        color='green',
        s=120,
        zorder=5,
        label=f'Peak Day ({peak_date.date()} : {peak_qty})'
    )

    # Labels & formatting
    ax.set_title("Number of Tickets Sold Per Day")
    ax.set_xlabel("Date")
    ax.set_ylabel("Tickets Sold")
    ax.legend()
    plt.xticks(rotation=45)

    st.pyplot(fig)

    # ---- KPI Metrics ----
    st.markdown("### 📊 Ticket Sales Insights")

    col1, col2, col3 = st.columns(3)
    col1.metric("Average / Day", f"{avg_tickets_per_day:.2f}")

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


    df['Date/Time (EDT)'] = pd.to_datetime(df['Date/Time (EDT)'])
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
    df = df.dropna(subset=['Price', 'Date/Time (EDT)'])
    df = df.sort_values(by='Date/Time (EDT)')


    # -------------------------
    # Total Tickets Sold per Zone
    # -------------------------
    st.markdown("## 🎟️ Total Tickets Sold per Zone")

    if 'Zone' in df.columns:
        tickets_by_zone = (
            df.groupby('Zone')['Qty']
            .sum()
            .reset_index()
            .sort_values('Qty', ascending=False)
        )

        tickets_by_zone.columns = ['Zone', 'Tickets Sold']

        st.dataframe(
            tickets_by_zone,
            use_container_width=True
        )

        # Optional: show top zone KPI
        top_zone = tickets_by_zone.iloc[0]
        st.metric(
            "🔥 Top-Selling Zone",
            top_zone['Zone'],
            f"{int(top_zone['Tickets Sold']):,} tickets"
        )
    else:
        st.warning("Zone column not found in the uploaded data.")

    

    # Plot 6: Ticket Quantity distribution
    st.write("## Ticket Quantity Distribution")
    fig6, ax6 = plt.subplots(figsize=(12, 6))
    sns.countplot(x="Qty", data=df, ax=ax6)
    st.pyplot(fig6)
