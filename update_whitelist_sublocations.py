from pyzscaler import ZIA
from requests.exceptions import HTTPError, RequestException
import time
import json

# === Credentials ===
zia = ZIA(
    api_key='your_api_key_here',
    cloud='zscaler',
    username='your_admin_username',
    password='your_admin_password',
    request_kwargs={'timeout': 10}
)

CLOUD = 'zscaler.net'
BASE_URL = f"https://zsapi.{CLOUD}/api/v1"
MAX_RETRIES = 5

def handle_rate_limit_with_backoff(response, attempt, base_delay=10):
    if response.status_code == 429:
        delay = base_delay * (2 ** attempt)
        print(f"⏳ Rate limit hit (attempt {attempt + 1}). Waiting {delay} seconds...")
        time.sleep(delay)
        return True
    return False

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

try:
    session = zia._session
    locations = zia.locations.list_locations()
    print(f"🌐 Total locations fetched: {len(locations)}")

    for loc in locations:
        loc_id = loc.get('id')
        loc_name = loc.get('name')
        print(f"\n📍 Checking sublocations for: {loc_name} (ID: {loc_id})")

        subloc_url = f"{BASE_URL}/locations/{loc_id}/sublocations?page=1&pageSize=100"
        for attempt in range(MAX_RETRIES):
            try:
                response = session.get(subloc_url, verify=False)
                if handle_rate_limit_with_backoff(response, attempt):
                    continue
                response.raise_for_status()
                sublocations = response.json()
                break
            except (HTTPError, RequestException) as e:
                if attempt == MAX_RETRIES - 1:
                    print(f"❌ Failed to fetch sublocations for {loc_name} after {MAX_RETRIES} attempts.")
                    sublocations = []
                    break

        for sub in sublocations:
            sub_name = sub.get('name', '')
            sub_id = sub.get('id')
            auth_required = sub.get('authRequired')

            if "Whitelist" in sub_name and auth_required is True:
                print(f"⚡ Detected: {sub_name} (ID: {sub_id})")

                full_url = f"{BASE_URL}/locations/{sub_id}"
                for attempt in range(MAX_RETRIES):
                    try:
                        full_resp = session.get(full_url, verify=False)
                        if handle_rate_limit_with_backoff(full_resp, attempt):
                            continue
                        full_resp.raise_for_status()
                        full_subloc = full_resp.json()
                        break
                    except (HTTPError, RequestException) as e:
                        if attempt == MAX_RETRIES - 1:
                            print(f"❌ Failed to get sublocation details for {sub_name}")
                            full_subloc = None
                            break

                if not full_subloc:
                    continue

                full_subloc['authRequired'] = False
                full_subloc['surrogateIP'] = False
                full_subloc['surrogateIPEnforcedForKnownBrowsers'] = False
                full_subloc, filled = sanitize_sublocation(full_subloc)
                if filled:
                    print(f"🛠 Filled: {', '.join(filled)}")

                for attempt in range(MAX_RETRIES):
                    try:
                        put_resp = session.put(full_url, json=full_subloc, verify=False)
                        if handle_rate_limit_with_backoff(put_resp, attempt):
                            continue
                        if put_resp.status_code == 200:
                            print(f"✅ Updated {sub_name}")
                        else:
                            print(f"❌ Failed to update {sub_name}. Status: {put_resp.status_code} Response: {put_resp.text}")
                        break
                    except (HTTPError, RequestException) as e:
                        if attempt == MAX_RETRIES - 1:
                            print(f"❌ PUT failed on {sub_name} after retries: {e}")
            else:
                print(f"✔️ No update needed for: {sub_name}")

        time.sleep(0.5)

except Exception as e:
    print("❌ Unexpected error occurred.")
    print(str(e))