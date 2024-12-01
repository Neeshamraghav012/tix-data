import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Set Streamlit page configuration
st.set_page_config(page_title="Ticket Data Analysis", layout="wide")

# Title of the app
st.title("Ticket Data Analysis Dashboard")

# File uploader
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file:
    # Read the uploaded file
    df = pd.read_csv(uploaded_file)
    
    st.write("### Data Preview")
    st.dataframe(df.head())  # Display the first 5 rows of the DataFrame

    # Set Seaborn and Matplotlib styles
    sns.set_style("darkgrid")
    plt.style.use("dark_background")

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

    # Plot 3: Average Price Over Time (with smoothing)
    st.write("## Average Price Over Time")
    df['Date/Time (EDT)'] = pd.to_datetime(df['Date/Time (EDT)'])  # Ensure datetime format
    df['Smoothed_Price'] = df['Price'].rolling(window=5).mean()  # Apply smoothing
    fig3, ax3 = plt.subplots(figsize=(12, 6))
    sns.lineplot(x="Date/Time (EDT)", y="Smoothed_Price", data=df, ax=ax3)
    plt.xticks(rotation=45)
    st.pyplot(fig3)

    # Plot 4: Ticket Quantity distribution
    st.write("## Ticket Quantity Distribution")
    fig4, ax4 = plt.subplots(figsize=(12, 6))
    sns.countplot(x="Qty", data=df, ax=ax4)
    st.pyplot(fig4)
