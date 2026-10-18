import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.express as px
from datetime import datetime
import plotly.graph_objects as go
import requests
import os
from dotenv import load_dotenv

load_dotenv()


def rerun_app():
    """Rerun the app across old and new Streamlit versions."""
    rerun_func = getattr(st, "rerun", None)
    if rerun_func is None:
        rerun_func = getattr(st, "experimental_rerun", None)

    if rerun_func is not None:
        rerun_func()


# --- Streamlit Page Config ---
st.set_page_config(page_title="Tickoo Dashboard", layout="wide")


# --- Title and Description ---
st.title("🎟️ Tickoo Analytics Dashboard")
st.markdown("""
Welcome to **Tickoo**, your smart ticket analytics dashboard!  
Upload your CSV file below to explore sales insights, price trends, and section-wise analytics — all interactively.
""")



# ==========================================
# DATA SOURCE
# ==========================================

st.markdown("## 📥 Load Ticket Data")

SEATDATA_API_KEY = os.getenv("SEATDATA_API_KEY", "")
SEATDATA_API_URL = "https://seatdata.io/api/v1/events/search"


def normalize_seatdata_columns(dataframe):
    """
    Try to normalize common API column names to the column names
    expected by the existing Tickoo analytics dashboard.
    """

    if dataframe is None or dataframe.empty:
        return dataframe

    df_copy = dataframe.copy()

    # Flatten nested dictionary column names if any.
    df_copy.columns = [
        str(col).replace(".", "_").strip()
        for col in df_copy.columns
    ]

    aliases = {
        "Price": [
            "price", "ticket_price", "listing_price",
            "current_price", "amount", "cost"
        ],
        "Qty": [
            "qty", "quantity", "tickets", "ticket_quantity",
            "available_quantity", "available_qty"
        ],
        "Section": [
            "section", "section_name", "seat_section",
            "section_id"
        ],
        "Zone": [
            "zone", "zone_name", "area", "level",
            "ticket_zone"
        ],
        "Date/Time (EDT)": [
            "date_time", "datetime", "timestamp",
            "created_at", "recorded_at", "scraped_at",
            "date"
        ]
    }

    # Case-insensitive column matching.
    lower_map = {
        str(col).lower(): col
        for col in df_copy.columns
    }

    rename_map = {}

    for target, possible_names in aliases.items():

        if target in df_copy.columns:
            continue

        for alias in possible_names:
            if alias.lower() in lower_map:
                rename_map[lower_map[alias.lower()]] = target
                break

    df_copy = df_copy.rename(columns=rename_map)

    return df_copy


def extract_records(response_data):
    """
    Extract the most likely list of ticket/listing records from
    different possible SeatData API response structures.
    """

    if isinstance(response_data, list):
        return response_data

    if not isinstance(response_data, dict):
        return []

    # Check common keys first.
    preferred_keys = [
        "data",
        "results",
        "events",
        "historical_data",
        "listings",
        "records",
        "tickets"
    ]

    for key in preferred_keys:
        value = response_data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            nested = extract_records(value)
            if nested:
                return nested

    # Search nested values as a fallback.
    for value in response_data.values():
        if isinstance(value, list) and value:
            return value

        if isinstance(value, dict):
            nested = extract_records(value)
            if nested:
                return nested

    return []




def get_event_candidates(records):
    """
    Build a unique list of events from API records.

    This supports several possible SeatData response structures.
    If the API returns multiple events for a venue, the user can
    select the exact event before the analytics data is loaded.
    """

    candidates = []
    seen = set()

    event_name_keys = [
        "event_name", "event.name", "event_title",
        "name", "title"
    ]

    venue_keys = [
        "venue_name", "venue.name", "venue",
        "stadium", "location_name"
    ]

    date_keys = [
        "event_date", "event.date", "event_datetime",
        "event.datetime", "date", "datetime"
    ]

    event_id_keys = [
        "event_id", "event.id", "id"
    ]


    def get_value(record, keys):

        for key in keys:

            # Support flattened keys.
            if key in record and record[key] not in [None, ""]:
                return record[key]

            # Support nested values such as {"event": {"name": ...}}
            if "." in key:

                parent, child = key.split(".", 1)

                if (
                    isinstance(record.get(parent), dict)
                    and record[parent].get(child) not in [None, ""]
                ):
                    return record[parent][child]

        return None


    for record in records:

        if not isinstance(record, dict):
            continue

        name = get_value(record, event_name_keys)
        venue = get_value(record, venue_keys)
        event_date_value = get_value(record, date_keys)
        event_id = get_value(record, event_id_keys)

        # Skip records that do not appear to describe an event.
        if not name and not event_id:
            continue

        unique_key = (
            str(event_id or ""),
            str(name or ""),
            str(venue or ""),
            str(event_date_value or "")
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)

        candidates.append({
            "event_id": event_id,
            "event_name": name,
            "venue_name": venue,
            "event_date": event_date_value,
            "unique_key": unique_key
        })

    return candidates


def format_event_candidate(candidate):

    parts = []

    if candidate.get("event_name"):
        parts.append(str(candidate["event_name"]))

    if candidate.get("venue_name"):
        parts.append(str(candidate["venue_name"]))

    if candidate.get("event_date"):
        parts.append(str(candidate["event_date"]))

    return " | ".join(parts) if parts else "Unnamed Event"


def filter_records_for_event(records, candidate):
    """
    Filter API records to the event selected by the user.
    Works when the API response already contains listings/history
    for multiple events.
    """

    selected_event_id = candidate.get("event_id")
    selected_name = candidate.get("event_name")
    selected_venue = candidate.get("venue_name")
    selected_date = candidate.get("event_date")

    filtered = []

    for record in records:

        if not isinstance(record, dict):
            continue

        # Reuse candidate extraction for this individual record.
        record_candidates = get_event_candidates([record])

        if not record_candidates:
            continue

        record_event = record_candidates[0]

        matches = True

        if selected_event_id is not None:
            matches = matches and (
                str(record_event.get("event_id"))
                == str(selected_event_id)
            )
        else:
            if selected_name:
                matches = matches and (
                    str(record_event.get("event_name"))
                    == str(selected_name)
                )

            if selected_venue:
                matches = matches and (
                    str(record_event.get("venue_name"))
                    == str(selected_venue)
                )

            if selected_date:
                matches = matches and (
                    str(record_event.get("event_date"))
                    == str(selected_date)
                )

        if matches:
            filtered.append(record)

    return filtered

# Keep API results available after Streamlit reruns.
if "loaded_df" not in st.session_state:
    st.session_state["loaded_df"] = None

if "data_source_name" not in st.session_state:
    st.session_state["data_source_name"] = "tickoo_data"

if "seatdata_records" not in st.session_state:
    st.session_state["seatdata_records"] = None

if "seatdata_candidates" not in st.session_state:
    st.session_state["seatdata_candidates"] = None


data_source = st.radio(
    "Choose data source",
    ["📁 Upload CSV", "🔎 Search SeatData API"],
    horizontal=True,
    index=1
)


# ==========================================
# CSV UPLOAD
# ==========================================

if data_source == "📁 Upload CSV":

    uploaded_file = st.file_uploader(
        "Upload your CSV file",
        type=["csv"]
    )

    if uploaded_file is not None:

        try:
            uploaded_df = pd.read_csv(uploaded_file)

            st.session_state["loaded_df"] = uploaded_df
            st.session_state["data_source_name"] = (
                uploaded_file.name.rsplit(".", 1)[0]
            )

        except Exception as e:
            st.error(f"Could not read CSV file: {e}")


# ==========================================
# SEATDATA API SEARCH
# ==========================================

else:

    st.markdown("### 🔎 Search Historical Event Data")

    col1, col2, col3 = st.columns(3)

    with col1:
        event_name = st.text_input(
            "🎤 Event Name",
            placeholder="e.g. Taylor Swift"
        )

    with col2:
        venue_name = st.text_input(
            "🏟️ Venue Name",
            placeholder="e.g. MetLife Stadium"
        )

    with col3:
        use_date = st.checkbox("Add Event Date Filter")
        event_date = None

        if use_date:
            event_date = st.date_input(
                "📅 Event Date"
            )


    search_button = st.button(
        "🔎 Search Event Data",
        type="primary",
        use_container_width=True
    )


    if search_button:

        # At least one search field is required.
        if not event_name.strip() and not venue_name.strip():

            st.error(
                "Please enter at least an Event Name or Venue Name."
            )

        elif not SEATDATA_API_KEY:

            st.error(
                "Set the SEATDATA_API_KEY environment variable before running "
                "the dashboard."
            )

        else:

            try:

                params = {
                    "historical": "false"  # Default to false; can be adjusted if needed
                }

                # Add only the fields supplied by the user.
                if event_name.strip():
                    params["event_name"] = event_name.strip()

                if venue_name.strip():
                    params["venue_name"] = venue_name.strip()

                if event_date is not None:
                    params["event_date"] = event_date.strftime(
                        "%Y-%m-%d"
                    )


                with st.spinner(
                    "Searching SeatData historical data..."
                ):

                    resp = requests.get(
                        SEATDATA_API_URL,
                        headers={
                            "Authorization": (
                                f"Bearer {SEATDATA_API_KEY}"
                            )
                        },
                        params=params,
                        timeout=30
                    )

                    resp.raise_for_status()

                    response_data = resp.json()


                records = extract_records(response_data)

                if records:

                    # Save raw API records so the user can select
                    # an event after the API request completes.
                    st.session_state["seatdata_records"] = records

                    candidates = get_event_candidates(records)

                    # If the response has identifiable multiple events,
                    # save them for the event selector.
                    if len(candidates) > 1:

                        st.session_state[
                            "seatdata_candidates"
                        ] = candidates

                        st.session_state["loaded_df"] = None

                        st.success(
                            f"✅ Found {len(candidates):,} events. "
                            "Select one below."
                        )

                    else:

                        # Search results describe events; they are not necessarily
                        # sales records. Fetch sales history for the one event too.
                        selected_candidate = candidates[0] if candidates else None

                        if not selected_candidate:
                            st.error(
                                "An event result was found, but its details could not be identified."
                            )
                        else:
                            selected_event_id = selected_candidate.get("event_id")

                            if not selected_event_id:
                                st.error(
                                    "The event was found, but the API response did not include "
                                    "an event ID needed to retrieve sales data."
                                )
                            else:
                                sales_url = (
                                    f"https://seatdata.io/api/v1/events/"
                                    f"{selected_event_id}/sales"
                                )
                                all_records = []
                                sales_params = {"limit": 200}

                                try:
                                    with st.spinner("Loading event sales data..."):
                                        while True:
                                            sales_resp = requests.get(
                                                sales_url,
                                                headers={
                                                    "Authorization": f"Bearer {SEATDATA_API_KEY}"
                                                },
                                                params=sales_params,
                                                timeout=60,
                                            )
                                            sales_resp.raise_for_status()
                                            sales_payload = sales_resp.json()
                                            page_records = extract_records(sales_payload)
                                            all_records.extend(page_records)

                                            next_cursor = (
                                                sales_payload.get("next_cursor")
                                                if isinstance(sales_payload, dict)
                                                else None
                                            )
                                            if not next_cursor:
                                                break
                                            sales_params = {
                                                "limit": 200,
                                                "starting_after": next_cursor,
                                            }

                                    if not all_records:
                                        st.warning(
                                            "The event was found, but SeatData returned no sales records."
                                        )
                                        with st.expander("🔧 Sales API Response Debug"):
                                            st.json(sales_payload)
                                    else:
                                        api_df = normalize_seatdata_columns(
                                            pd.json_normalize(all_records)
                                        )
                                        required_api_columns = ["Qty", "Price", "Section"]
                                        missing_api_columns = [
                                            col for col in required_api_columns
                                            if col not in api_df.columns
                                        ]

                                        if missing_api_columns:
                                            st.error(
                                                "Sales data is missing required columns: "
                                                + ", ".join(missing_api_columns)
                                            )
                                            st.write("Available columns:", list(api_df.columns))
                                            with st.expander("🔧 First sales record"):
                                                st.json(all_records[0])
                                        else:
                                            if "Date/Time (EDT)" in api_df.columns:
                                                # Parse strings/datetimes normally; numeric timestamps as Unix seconds.
                                                date_values = api_df["Date/Time (EDT)"]
                                                if pd.api.types.is_numeric_dtype(date_values):
                                                    api_df["Date/Time (EDT)"] = pd.to_datetime(
                                                        date_values, unit="s", errors="coerce"
                                                    )
                                                else:
                                                    api_df["Date/Time (EDT)"] = pd.to_datetime(
                                                        date_values, errors="coerce"
                                                    )

                                            st.session_state["loaded_df"] = api_df
                                            st.session_state["seatdata_candidates"] = None
                                            st.session_state["seatdata_search"] = {
                                                "event_id": selected_event_id,
                                                "event_name": selected_candidate.get("event_name"),
                                                "venue_name": selected_candidate.get("venue_name"),
                                                "event_date": selected_candidate.get("event_date"),
                                            }

                                            filename_parts = [
                                                str(selected_candidate[key])
                                                for key in ("event_name", "venue_name", "event_date")
                                                if selected_candidate.get(key)
                                            ]
                                            st.session_state["data_source_name"] = (
                                                "_".join(filename_parts) or "seatdata_event"
                                            )
                                            st.success(
                                                f"✅ Loaded {len(api_df):,} sales records from SeatData."
                                            )
                                            rerun_app()

                                except requests.exceptions.HTTPError as e:
                                    status = (
                                        sales_resp.status_code
                                        if "sales_resp" in locals()
                                        else "unknown"
                                    )
                                    details = (
                                        sales_resp.text
                                        if "sales_resp" in locals()
                                        else str(e)
                                    )
                                    st.error(f"SeatData sales API error {status}: {details}")
                                except requests.exceptions.Timeout:
                                    st.error("The sales request timed out. Please try again.")
                                except requests.exceptions.RequestException as e:
                                    st.error(f"SeatData sales request failed: {e}")
                                except Exception as e:
                                    st.error(f"Could not load sales data: {e}")

                else:

                    st.warning(
                        "No records were found for this search."
                    )

                    with st.expander("🔧 API Response Debug"):
                        st.json(response_data)


            except requests.exceptions.HTTPError:

                st.error(
                    f"SeatData API Error {resp.status_code}: "
                    f"{resp.text}"
                )

            except requests.exceptions.Timeout:

                st.error(
                    "The SeatData request timed out. Please try again."
                )

            except requests.exceptions.RequestException as e:

                st.error(
                    f"SeatData request failed: {str(e)}"
                )

            except Exception as e:

                st.error(
                    f"Unexpected error: {str(e)}"
                )



# ==========================================
# EVENT SELECTOR
# ==========================================

if (
    data_source == "🔎 Search SeatData API"
    and st.session_state.get("seatdata_candidates")
):

    candidates = st.session_state["seatdata_candidates"]

    st.markdown("## 🎟️ Select the Event")

    candidate_options = {
        format_event_candidate(candidate): candidate
        for candidate in candidates
    }

    selected_event_label = st.selectbox(
        "Multiple events were found. Choose the event you want to analyze:",
        list(candidate_options.keys())
    )

    selected_candidate = candidate_options[
        selected_event_label
    ]

    if st.button(
        "📊 Load Selected Event",
        type="primary",
        use_container_width=True
    ):

        selected_event_id = selected_candidate.get("event_id")

        if not selected_event_id:

            st.error("Could not find the Event ID.")

        else:

            try:

                with st.spinner(
                    "Loading complete historical sales data..."
                ):

                    # ======================================
                    # SEATDATA SALES API
                    # ======================================

                    sales_url = (
                        f"https://seatdata.io/api/v1/events/"
                        f"{selected_event_id}/sales"
                    )

                    all_records = []

                    params = {
                        "limit": 200
                    }


                    # ======================================
                    # FETCH ALL PAGINATION PAGES
                    # ======================================

                    while True:

                        response = requests.get(
                            sales_url,
                            headers={
                                "Authorization": (
                                    f"Bearer {SEATDATA_API_KEY}"
                                )
                            },
                            params=params,
                            timeout=60
                        )

                        response.raise_for_status()

                        sales_response = response.json()


                        # Add current page records
                        page_records = sales_response.get(
                            "data",
                            []
                        )

                        all_records.extend(
                            page_records
                        )


                        # Get next cursor
                        next_cursor = sales_response.get(
                            "next_cursor"
                        )


                        # Stop when there are no more pages
                        if not next_cursor:
                            break


                        # Request next page
                        params = {
                            "limit": 200,
                            "starting_after": next_cursor
                        }


                    # ======================================
                    # CHECK DATA
                    # ======================================

                    if not all_records:

                        st.warning(
                            "No historical sales data was found "
                            "for this event."
                        )

                    else:

                        # Convert API data to DataFrame
                        api_df = pd.DataFrame(
                            all_records
                        )


                        # ======================================
                        # MAP SEATDATA COLUMNS
                        # ======================================

                        api_df = api_df.rename(
                            columns={
                                "quantity": "Qty",
                                "price": "Price",
                                "section": "Section",
                                "zone": "Zone",
                                "timestamp": "Date/Time (EDT)"
                            }
                        )


                        # ======================================
                        # CONVERT TIMESTAMP
                        # ======================================

                        api_df[
                            "Date/Time (EDT)"
                        ] = pd.to_datetime(
                            api_df[
                                "Date/Time (EDT)"
                            ],
                            unit="s",
                            errors="coerce"
                        )


                        # ======================================
                        # SAVE DATA
                        # ======================================

                        st.session_state[
                            "loaded_df"
                        ] = api_df


                        # Generate filename
                        filename_parts = []


                        if selected_candidate.get(
                            "event_name"
                        ):

                            filename_parts.append(
                                str(
                                    selected_candidate[
                                        "event_name"
                                    ]
                                )
                            )


                        if selected_candidate.get(
                            "venue_name"
                        ):

                            filename_parts.append(
                                str(
                                    selected_candidate[
                                        "venue_name"
                                    ]
                                )
                            )


                        if selected_candidate.get(
                            "event_date"
                        ):

                            filename_parts.append(
                                str(
                                    selected_candidate[
                                        "event_date"
                                    ]
                                )
                            )


                        st.session_state[
                            "data_source_name"
                        ] = (
                            "_".join(
                                filename_parts
                            )
                            or "seatdata_event"
                        )


                        # Save selected event metadata
                        st.session_state[
                            "seatdata_search"
                        ] = {

                            "event_id": selected_event_id,

                            "event_name": (
                                selected_candidate.get(
                                    "event_name"
                                )
                            ),

                            "venue_name": (
                                selected_candidate.get(
                                    "venue_name"
                                )
                            ),

                            "event_date": (
                                selected_candidate.get(
                                    "event_date"
                                )
                            )
                        }


                        # Remove event selector
                        st.session_state[
                            "seatdata_candidates"
                        ] = None


                        st.success(
                            f"✅ Loaded "
                            f"{len(api_df):,} historical "
                            f"sales records!"
                        )


                        # Rerun dashboard
                        rerun_app()


            except requests.exceptions.HTTPError:

                st.error(
                    f"SeatData API Error "
                    f"{response.status_code}: "
                    f"{response.text}"
                )


            except requests.exceptions.Timeout:

                st.error(
                    "The request timed out. "
                    "The event may have a large amount "
                    "of historical data."
                )


            except Exception as e:

                st.error(
                    f"Error loading sales data: {str(e)}"
                )


# ==========================================
# CLEAR CURRENT DATA
# ==========================================

if st.session_state["loaded_df"] is not None:

    if st.button("🗑️ Clear Current Data"):
        st.session_state["loaded_df"] = None
        st.session_state["seatdata_records"] = None
        st.session_state["seatdata_candidates"] = None
        rerun_app()


# ==========================================
# LOAD DATA INTO EXISTING DASHBOARD
# ==========================================

df = st.session_state["loaded_df"]

if df is not None and not df.empty:

    # Work on a copy so the original session data remains unchanged.
    df = df.copy()

    original_filename = st.session_state["data_source_name"]

    edited_filename = st.text_input(
        "📝 Edit file name (used for exports & reference)",
        value=original_filename
    )

    csv_data = df.to_csv(index=False).encode("utf-8")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    st.download_button(
        label="⬇️ Download Current Data",
        data=csv_data,
        file_name=f"{edited_filename}_{timestamp}.csv",
        mime="text/csv"
    )

    # Validate and prepare required columns.
    required_columns = ["Qty", "Price", "Section"]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:

        st.error(
            "The loaded data is missing required columns: "
            + ", ".join(missing_columns)
        )

        st.write("Available columns:")
        st.write(list(df.columns))

        st.info(
            "For SeatData API results, update the column aliases in "
            "normalize_seatdata_columns() after checking the actual "
            "API response structure."
        )

    else:

        # Ensure the expected datetime column exists.
        if "Date/Time (EDT)" not in df.columns:

            st.warning(
                "Date/Time (EDT) was not found. Creating a temporary "
                "timestamp from the current time so the dashboard can "
                "load. Update normalize_seatdata_columns() with the "
                "correct SeatData timestamp field for accurate "
                "historical analysis."
            )

            df["Date/Time (EDT)"] = pd.Timestamp.now()

        # ==========================================
        # EXISTING ANALYTICS CODE
        # ==========================================

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

        if df.empty:
            st.warning("No rows remain after cleaning the Qty and Price columns. Check the source data and column mappings.")
            st.stop()

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

        # --- Tickets Sold Today ---
        today_date = datetime.now().date()

        today_tickets = int(
            filtered_df[filtered_df['Date'] == today_date]['Qty'].sum()
        )

        # --- Tickets Sold Last Day (Previous Date) ---
        tickets_last_day = 0

        available_dates = sorted(filtered_df['Date'].dropna().unique())

        # Remove today from available dates
        previous_dates = [d for d in available_dates if d < today_date]

        if previous_dates:
            last_day_date = max(previous_dates)

            tickets_last_day = int(
                filtered_df[filtered_df['Date'] == last_day_date]['Qty'].sum()
            )

        # --- KPIs Section ---
        st.markdown("## 📊 Key Performance Indicators")
        col1, col2, col3, col4, col5 = st.columns(5)

        # Use filtered_df instead of df
        total_tickets = int(filtered_df['Qty'].sum())
        avg_price = round(filtered_df['Price'].mean(), 2) if not filtered_df.empty else 0
        highest_price = round(filtered_df['Price'].max(), 2) if not filtered_df.empty else 0

        with col1:
            st.metric("🎫 Total Tickets Sold", f"{total_tickets:,}")
        with col2:
            st.metric("💰 Average Ticket Price", f"${avg_price:,.0f}")
        with col3:
            st.metric("🏆 Highest Ticket Price", f"${highest_price:,.0f}")
        with col4:
            st.metric("📅 Tickets Sold (Last Day)", f"{tickets_last_day:,}")
        with col5:
            st.metric("🟢 Tickets Sold Today", f"{today_tickets:,}")


    
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

else:
    st.info('Load a CSV file or search SeatData to start analyzing ticket data.')
