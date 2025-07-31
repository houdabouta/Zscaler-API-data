import os
import json
import csv
import time
from pyzscaler import ZIA
from requests.exceptions import HTTPError, RequestException

# === Credentials ===
zia = ZIA(
    api_key='your_api_key_here'
    username='your_admin_username'
    password='your_admin_password'
    cloud='zscaler'  # or 'zscalerone', etc.
)

CLOUD = 'zscaler.net'
BASE_URL = f"https://zsapi.{CLOUD}/api/v1"
MAX_RETRIES = 5
OUTPUT_DIR = 'zia_outputs'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Rate limit handler
def handle_rate_limit(response, attempt, base_delay=10):
    if response.status_code == 429:
        delay = base_delay * (2 ** attempt)
        print(f"⏳ Rate limit hit (attempt {attempt + 1}). Waiting {delay} seconds...")
        time.sleep(delay)
        return True
    return False

print("🔄 Fetching locations from Zscaler...")
locations = zia.locations.list_locations()
print(f"🌐 Total locations fetched: {len(locations)}")

all_data = []
session = zia._session

for index, loc in enumerate(locations, 1):
    loc_id = loc.get('id')
    loc_name = loc.get('name')
    print(f"\n[{index}/{len(locations)}] 📍 Fetching details for: {loc_name} (ID: {loc_id})")

    # Fetch location details
    location_detail_url = f"{BASE_URL}/locations/{loc_id}"

    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(location_detail_url)
            if handle_rate_limit(response, attempt):
                continue
            response.raise_for_status()
            location_detail = response.json()
            break
        except (HTTPError, RequestException) as e:
            print(f"❌ Error fetching location details for {loc_name}: {e}")
            location_detail = {}

    # Fetch VPN credentials for the location
    vpn_cred_url = f"{BASE_URL}/locations/{loc_id}/vpnCredentials"
    vpn_credentials = []

    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(vpn_cred_url)
            if handle_rate_limit(response, attempt):
                continue
            if response.status_code == 404:
                # No VPN credentials for this location
                break
            response.raise_for_status()
            vpn_credentials = response.json()
            break
        except (HTTPError, RequestException) as e:
            if isinstance(e, HTTPError) and e.response.status_code == 404:
                break  # Skip, no VPN credentials
            print(f"❌ Error fetching VPN credentials for {loc_name}: {e}")
            break

    # Fetch Sublocations
    sublocation_url = f"{BASE_URL}/locations/{loc_id}/sublocations?page=1&pageSize=100"

    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(sublocation_url)
            if handle_rate_limit(response, attempt):
                continue
            response.raise_for_status()
            sublocations = response.json()
            break
        except (HTTPError, RequestException) as e:
            print(f"❌ Error fetching sublocations for {loc_name}: {e}")
            sublocations = []

    combined_data = {
        'location_id': loc_id,
        'location_name': loc_name,
        'location_detail': location_detail,
        'vpn_credentials': vpn_credentials,
        'sublocations': sublocations
    }

    all_data.append(combined_data)

    # Save individual file
    temp_json_path = os.path.join(OUTPUT_DIR, f"location_{loc_id}.json")
    with open(temp_json_path, 'w') as json_file:
        json.dump(combined_data, json_file, indent=2)

# Save merged data
merged_json_path = os.path.join(OUTPUT_DIR, 'all_locations_data.json')
with open(merged_json_path, 'w') as merged_json_file:
    json.dump(all_data, merged_json_file, indent=2)

# Generate CSV
csv_path = os.path.join(OUTPUT_DIR, 'locations_vpn_credentials.csv')
with open(csv_path, 'w', newline='', encoding='utf-8') as csv_file:
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow([
        'Location ID', 'Location Name',
        'VPN FQDN', 'Pre Shared Key',
        'Sublocation ID', 'Sublocation Name', 'Country', 'Time Zone',
        'Auth Required', 'Surrogate IP', 'XFF Forward Enabled',
        'IP Addresses', 'Profile'
    ])

    for entry in all_data:
        vpn_creds = entry.get('vpn_credentials', [])
        sublocs = entry.get('sublocations', [])

        if not sublocs:
            for vpn in vpn_creds or [{}]:
                csv_writer.writerow([
                    entry['location_id'], entry['location_name'],
                    vpn.get('fqdn', ''), vpn.get('preSharedKey', ''),
                    '', '', '', '', '', '', '', '', ''
                ])
        else:
            for sub in sublocs:
                for vpn in vpn_creds or [{}]:
                    csv_writer.writerow([
                        entry['location_id'], entry['location_name'],
                        vpn.get('fqdn', ''), vpn.get('preSharedKey', ''),
                        sub.get('id', ''), sub.get('name', ''),
                        sub.get('country', ''), sub.get('tz', ''),
                        sub.get('authRequired', ''), sub.get('surrogateIP', ''),
                        sub.get('xffForwardEnabled', ''),
                        ', '.join(sub.get('ipAddresses', [])),
                        sub.get('profile', '')
                    ])

print(f"✅ CSV generation completed: {csv_path}")
