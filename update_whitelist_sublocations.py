from pyzscaler import ZIA
from requests.exceptions import HTTPError, RequestException
import time
import json

# === Credentials ===
zia = ZIA(
    api_key='your_api_key_here',
    cloud='zscaler',  # or 'zscalerone', etc.
    username='your_admin_username',
    password='your_admin_password',
    request_kwargs={'timeout': 10}
)
CLOUD = 'zscaler.net'
BASE_URL = f"https://zsapi.{CLOUD}/api/v1"
RATE_LIMIT_WAIT = 15  # seconds to wait on 429 responses

# === Helper: Sanitize sublocation object ===
def sanitize_sublocation(subloc):
    fields_filled = []

    if not subloc.get('profile'):
        subloc['profile'] = 'CORPORATE'
        fields_filled.append('profile')

    if not subloc.get('tz'):
        subloc['tz'] = 'FRANCE_EUROPE_PARIS'
        fields_filled.append('tz')

    if not subloc.get('country'):
        subloc['country'] = 'FRANCE'
        fields_filled.append('country')

    if not subloc.get('ipAddresses') or not isinstance(subloc['ipAddresses'], list):
        subloc['ipAddresses'] = ["0.0.0.0-0.0.0.0"]
        fields_filled.append('ipAddresses')

    if 'surrogateIP' not in subloc:
        subloc['surrogateIP'] = False
        fields_filled.append('surrogateIP')

    if 'authRequired' not in subloc:
        subloc['authRequired'] = False
        fields_filled.append('authRequired')

    if 'surrogateIPEnforcedForKnownBrowsers' not in subloc:
        subloc['surrogateIPEnforcedForKnownBrowsers'] = False
        fields_filled.append('surrogateIPEnforcedForKnownBrowsers')

    if 'xffForwardEnabled' not in subloc:
        subloc['xffForwardEnabled'] = False
        fields_filled.append('xffForwardEnabled')

    return subloc, fields_filled

# === Helper: Handle rate limit ===
def handle_rate_limit(response):
    if response.status_code == 429:
        print("⏳ Rate limit hit. Waiting before retrying...")
        time.sleep(RATE_LIMIT_WAIT)
        return True
    return False

try:
    session = zia._session
    locations = zia.locations.list_locations()
    print(f"🌐 Total locations fetched: {len(locations)}")

    for loc in locations:
        loc_id = loc.get('id')
        loc_name = loc.get('name')

        print(f"\n📍 Checking sublocations for: {loc_name} (ID: {loc_id})")

        subloc_url = f"{BASE_URL}/locations/{loc_id}/sublocations?page=1&pageSize=100"
        while True:
            try:
                response = session.get(subloc_url, verify=False)
                if handle_rate_limit(response):
                    continue
                response.raise_for_status()
                sublocations = response.json()
                break
            except HTTPError as e:
                print(f"❌ HTTP error on sublocations for {loc_name}. Status: {e.response.status_code}")
                print(e.response.text)
                break
            except RequestException as e:
                print(f"❌ Request failed for sublocations of {loc_name}: {e}")
                break

        for sub in sublocations:
            sub_name = sub.get('name', '')
            sub_id = sub.get('id')
            auth_required = sub.get('authRequired')

            if "Whitelist" in sub_name and auth_required is True:
                print(f"⚡ Detected: {sub_name} (ID: {sub_id}) with authRequired=True. Preparing update...")

                full_url = f"{BASE_URL}/locations/{sub_id}"
                while True:
                    try:
                        full_resp = session.get(full_url, verify=False)
                        if handle_rate_limit(full_resp):
                            continue
                        full_resp.raise_for_status()
                        full_subloc = full_resp.json()
                        break
                    except HTTPError as e:
                        print(f"❌ HTTP error on fetching sublocation {sub_name}. Status: {e.response.status_code}")
                        print(e.response.text)
                        break
                    except RequestException as e:
                        print(f"❌ Request failed for sublocation {sub_name}: {e}")
                        break

                print(f"🔵 Old authRequired: {full_subloc.get('authRequired')}")
                print(f"🔵 Old surrogateIP: {full_subloc.get('surrogateIP')}")
                print(f"🔵 Old surrogateIPEnforcedForKnownBrowsers: {full_subloc.get('surrogateIPEnforcedForKnownBrowsers')}")

                # Apply changes
                full_subloc['authRequired'] = False
                full_subloc['surrogateIP'] = False
                full_subloc['surrogateIPEnforcedForKnownBrowsers'] = False

                full_subloc, filled_fields = sanitize_sublocation(full_subloc)

                if filled_fields:
                    print(f"🛠 Filled missing fields: {', '.join(filled_fields)}")

                while True:
                    try:
                        put_resp = session.put(full_url, json=full_subloc, verify=False)
                        if handle_rate_limit(put_resp):
                            continue
                        if put_resp.status_code == 200:
                            print(f"✅ Successfully updated {sub_name}")
                        else:
                            print(f"❌ Failed to update {sub_name}. Status: {put_resp.status_code} Response: {put_resp.text}")
                        break
                    except HTTPError as e:
                        print(f"❌ HTTP error while updating {sub_name}. Status: {e.response.status_code}")
                        print(e.response.text)
                        break
                    except RequestException as e:
                        print(f"❌ Update request failed for {sub_name}: {e}")
                        break
            else:
                print(f"✔️ No update needed for: {sub_name}")

        time.sleep(0.5)

except Exception as e:
    print("❌ Unexpected error occurred.")
    print(str(e))