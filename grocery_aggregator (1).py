# -*- coding: utf-8 -*-
"""Grocery Price Aggregator

This script creates a Streamlit web application for aggregating grocery prices.
It features a simulation mode using mock data and integration capability for the
Kroger API (requires client ID and secret).
"""

import streamlit as st
import pandas as pd
import random
import requests
import base64
import time
import altair as alt

# --- APP CONFIGURATION ---
st.set_page_config(
    page_title="Local Grocery Price Aggregator",
    page_icon="🛒",
    layout="wide"
)

# --- MOCK DATA GENERATOR (SIMULATION MODE) ---
# This allows the user to test the app without needing API keys immediately.
def get_mock_stores(zip_code):
    """Generates fake stores based on a zip code to demonstrate functionality."""
    random.seed(zip_code) # Seed so the same zip always yields the same 'random' stores
    store_chains = ["Kroger", "Walmart", "Aldi", "Whole Foods", "Trader Joe's", "Safeway"]

    # Randomly select 3-5 stores for this area
    num_stores = random.randint(3, 5)
    selected_chains = random.sample(store_chains, num_stores)

    stores = []
    for chain in selected_chains:
        stores.append({
            "name": chain,
            "location_id": f"LOC-{random.randint(1000, 9999)}",
            "address": f"{random.randint(100, 999)} Main St, Zip {zip_code}",
            "distance": f"{random.randint(1, 10)} miles"
        })
    return stores

def get_mock_prices(item_name, stores):
    """Generates fake prices for an item across the found stores."""
    random.seed(item_name) # Seed so "Milk" always costs the same in a session

    results = []
    base_price = random.uniform(2.50, 15.00) # Random base price for the item

    for store in stores:
        # Vary price by +/- 20% per store to simulate competition
        variance = random.uniform(0.8, 1.2)
        price = round(base_price * variance, 2)

        # Simulate stock status
        in_stock = random.choice([True, True, True, False])

        if in_stock:
            results.append({
                "Store": store['name'],
                "Item": item_name.title(),
                "Price": price,
                "Address": store['address'],
                "Stock": "In Stock"
            })
        else:
            results.append({
                "Store": store['name'],
                "Item": item_name.title(),
                "Price": None,
                "Address": store['address'],
                "Stock": "Out of Stock"
            })

    return pd.DataFrame(results)

# --- REAL KROGER API INTEGRATION ---
# This class handles the connection if the user provides keys.
class KrogerAPI:
    def __init__(self, client_id, client_secret):
        self.base_url = "https://api-ce.kroger.com/v1"
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = self._get_access_token()

    def _get_access_token(self):
        """Authenticates with Kroger using Client Credentials."""
        url = f"{self.base_url}/connect/oauth2/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {self._encode_credentials()}"
        }
        data = {"grant_type": "client_credentials", "scope": "product.compact"}

        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            return response.json().get("access_token")
        except Exception as e:
            st.error(f"Authentication Failed: {e}")
            return None

    def _encode_credentials(self):
        credentials = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(credentials.encode()).decode()

    def get_locations(self, zip_code, radius_miles=10):
        """Fetches real store locations near a zip code."""
        if not self.token: return []

        url = f"{self.base_url}/locations"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.token}"}
        params = {"filter.zipCode.near": zip_code, "filter.limit": 5, "filter.radiusInMiles": radius_miles}

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json().get('data', [])
            stores = []
            for d in data:
                stores.append({
                    "name": d.get('name'),
                    "location_id": d.get('locationId'),
                    "address": d.get('address', {}).get('addressLine1', 'Unknown')
                })
            return stores
        return []

    def get_product_price(self, term, location_id):
        """Fetches product price for a specific store location."""
        if not self.token: return None

        url = f"{self.base_url}/products"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.token}"}
        params = {"filter.term": term, "filter.locationId": location_id, "filter.limit": 1}

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json().get('data', [])
            if data:
                # Extracting the regular price from the first result
                items = data[0].get('items', [])
                if items:
                    price_info = items[0].get('price', {}).get('regular', 0)
                    return price_info
        return None

# --- MAIN APP UI ---

st.title("🛒 Smart Grocery Aggregator")
st.markdown("""
Compare grocery prices across stores near you.
**Note:** Real-time data requires API keys. Use 'Simulation Mode' to test the app logic.
""")

# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("Settings")
    mode = st.radio("Data Source", ["Simulation Mode (Mock Data)", "Real Kroger API"])

    user_zip = st.text_input("Enter Zip Code", "90210")

    client_id = ""
    client_secret = ""

    if mode == "Real Kroger API":
        st.info("To get keys, visit: developer.kroger.com")
        client_id = st.text_input("Kroger Client ID", type="password")
        client_secret = st.text_input("Kroger Client Secret", type="password")

# --- APP LOGIC ---

if user_zip:
    st.divider()
    st.subheader(f"📍 Stores near {user_zip}")

    stores = []

    # 1. FETCH STORES
    if mode == "Simulation Mode (Mock Data)":
        stores = get_mock_stores(user_zip)
        st.success(f"Found {len(stores)} stores (Simulated)")

    elif mode == "Real Kroger API" and client_id and client_secret:
        with st.spinner("Connecting to Kroger API..."):
            api = KrogerAPI(client_id, client_secret)
            stores = api.get_locations(user_zip)
            if stores:
                st.success(f"Found {len(stores)} Kroger locations.")
            else:
                st.warning("No stores found or API Error.")

    # Display Stores found
    if stores:
        store_df = pd.DataFrame(stores)
        st.dataframe(store_df[['name', 'address']], use_container_width=True)

        # 2. SEARCH PRODUCTS
        st.divider()
        st.subheader("🔍 Compare Item Prices")

        item_query = st.text_input("What are you looking for?", placeholder="e.g., Milk, Bread, Eggs")
        search_btn = st.button("Find Cheapest Price")

        if search_btn and item_query:
            price_data = []

            with st.spinner(f"Checking prices for '{item_query}'..."):
                if mode == "Simulation Mode (Mock Data)":
                    time.sleep(1.0) # Fake network delay for realism
                    df_prices = get_mock_prices(item_query, stores)

                elif mode == "Real Kroger API":
                    # Logic to fetch real prices from the found locations
                    real_results = []
                    progress_bar = st.progress(0)
                    if 'api' in locals():
                        for i, store in enumerate(stores):
                            price = api.get_product_price(item_query, store['location_id'])
                            real_results.append({
                                "Store": store['name'],
                                "Item": item_query,
                                "Price": price if price else None,
                                "Address": store['address'],
                                "Stock": "Unknown"
                            })
                            progress_bar.progress((i + 1) / len(stores))
                        df_prices = pd.DataFrame(real_results)
                    else:
                         st.error("API object not initialized. Check your credentials.")
                         df_prices = pd.DataFrame()


            # 3. DISPLAY RESULTS
            if not df_prices.empty:
                # Clean up data for display (remove out of stock for the chart)
                valid_prices = df_prices.dropna(subset=['Price']).sort_values(by='Price')

                if not valid_prices.empty:
                    best_deal = valid_prices.iloc[0]
                    st.metric(
                        label="🏆 Best Price Found At",
                        value=f"${best_deal['Price']:.2f}",
                        delta=best_deal['Store']
                    )

                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.markdown("### Price Comparison")
                        # Adjust chart to explicitly use the Item title
                        chart = alt.Chart(valid_prices).mark_bar().encode(
                            x=alt.X('Store', sort='y'),
                            y=alt.Y('Price', axis=alt.Axis(format='$%.2f')),
                            color=alt.Color('Store'),
                            tooltip=['Store', 'Price', 'Address']
                        ).properties(
                            height=300,
                            title=f"Price Comparison for {item_query.title()}"
                        ).interactive()
                        st.altair_chart(chart, use_container_width=True)

                    with col2:
                        st.markdown("### Details")
                        st.dataframe(
                            df_prices[['Store', 'Price', 'Stock']].style.format({"Price": "${:.2f}"}),
                            use_container_width=True
                        )
                else:
                    st.error(f"Could not find a price for '{item_query}' at any location.")
            elif search_btn:
                st.error("No data could be retrieved. Please check your inputs or API keys.")
    else:
        st.info("Enter a valid zip code to find stores.")
else:
    st.info("Please enter a zip code in the sidebar to begin.")