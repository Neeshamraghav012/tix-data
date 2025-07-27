import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Set Streamlit page configuration
st.set_page_config(page_title="Ticku", layout="wide")

# Title of the app
st.title("Ticku Dashboard")

# File uploader
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file:
    # Read the uploaded file
    df = pd.read_csv(uploaded_file)

    # Convert 'Qty' and 'Price' to numeric
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce')
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')

    # Remove rows where Qty or Price is zero or NaN
    df = df[(df['Qty'] > 0) & (df['Price'].notna())]

    # --- Remove Outliers from Price only ---
    Q1 = df['Price'].quantile(0.25)
    Q3 = df['Price'].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    df = df[(df['Price'] >= lower_bound) & (df['Price'] <= upper_bound)]


    st.write("### Data Preview")
    st.dataframe(df.head())  # Display the first 5 rows of the DataFrame

    # Total number of sales
    total_tickets_sold = df['Qty'].sum()
    st.write(f"### Total tickets Sold: {total_tickets_sold}")

    # Calculate min and max prices per section
    price_stats = df.groupby('Section')['Price'].agg(['min', 'max']).reset_index()
    st.write("### Min and Max Prices Per Section")
    st.dataframe(price_stats)

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
    sns.scatterplot(x="Section", y="Price", data=df_top, ax=ax2, palette="coolwarm", s=100)  # Adjust size for clarity
    ax2.set_title("Price Variation for Top Sections")
    ax2.set_xticklabels(ax2.get_xticklabels(), rotation=45, ha='right')  # Rotate labels for readability
    st.pyplot(fig2)

    # Plot 3: Price variation per section (Violin Plot)
    st.write("## Price Variation Per Section (Violin Plot)")
    fig3, ax3 = plt.subplots(figsize=(16, 6))
    sns.violinplot(x="Section", y="Price", data=df_top, ax=ax3, palette="coolwarm")
    ax3.set_xticklabels(ax3.get_xticklabels(), rotation=45, ha='right')  # Rotate labels for readability
    ax3.set_title("Price Distribution Per Section")
    st.pyplot(fig3)

    df['Date/Time (EDT)'] = pd.to_datetime(df['Date/Time (EDT)'])  # Ensure datetime format
    
    # Ensure 'Price' is numeric
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')

    # Drop rows with missing values in 'Price' or 'Date/Time (EDT)'
    df = df.dropna(subset=['Price', 'Date/Time (EDT)'])

    # Sort by datetime before rolling
    df = df.sort_values(by='Date/Time (EDT)')
   

    # Plot 5: Average Price Over Time (with smoothing)
    st.write("## Average Price Over Time")
    df['Smoothed_Price'] = df['Price'].rolling(window=5).mean()  # Apply smoothing
    fig5, ax5 = plt.subplots(figsize=(12, 6))
    sns.lineplot(x="Date/Time (EDT)", y="Smoothed_Price", data=df, ax=ax5)
    plt.xticks(rotation=45)
    st.pyplot(fig5)

    # Plot: Separate Time Series of Price Over Time for Each Zone (with different colors)
    st.write("## Price Over Time for Each Zone")

    if 'Zone' in df.columns:
        import itertools
        # Define a list of distinct colors (extend if you have more zones)
        color_list = sns.color_palette("Set2", n_colors=10)
        color_cycle = itertools.cycle(color_list)  # Create a cycle of colors

        # Filter to top zones to avoid too many graphs
        top_zones = df['Zone'].value_counts().nlargest(5).index
        df_zone_time = df[df['Zone'].isin(top_zones)]

        for zone in top_zones:
            st.write(f"### Zone: {zone}")
            zone_df = df_zone_time[df_zone_time['Zone'] == zone]

            fig, ax = plt.subplots(figsize=(14, 5))
            color = next(color_cycle)  # Get next color for each plot
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
