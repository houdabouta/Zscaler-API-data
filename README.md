# Zscaler-API-
This script iterates through all configured locations in Zscaler Internet Access (ZIA), identifies sublocations with `"Whitelist"` in their name and `authRequired = True`, and disables authentication and surrogate IP enforcement for those sublocations.

## 🔧 Features

- Uses the Zscaler REST API (via `pyzscaler`)
- Handles rate limits (`429 Too Many Requests`)
- Automatically fills required fields if missing
- Provides detailed logging of each operation

## 📂 File Structure

- `update_whitelist_sublocations.py`: Main script
- `requirements.txt`: Python dependencies

## 📋 Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

## 🔐 Setup

Edit the `update_whitelist_sublocations.py` file and replace the following placeholders:

```python
api_key='your_api_key_here'
username='your_admin_username'
password='your_admin_password'
cloud='zscaler'  # or 'zscalerone', etc.
```

You can find your API key and credentials in the ZIA Admin GUI under **Administration > Cloud Service API**.

## ▶️ Usage

```bash
python update_whitelist_sublocations.py
```

## 📌 Notes

- This script disables:
  - `authRequired`
  - `surrogateIP`
  - `surrogateIPEnforcedForKnownBrowsers`
- Only applies to sublocations that have `"Whitelist"` in their name and currently have authentication enabled.

## ⚠️ API Rate Limits

ZIA API limits apply. This script implements backoff when HTTP 429 errors are encountered.

## ✅ Example Output

```
📍 Checking sublocations for: Paris HQ (ID: 12345678)
⚡ Updating: Paris-Guest-Whitelist (ID: 87654321)
🔵 Old authRequired: True
🛠 Filled: profile, tz
✅ Updated Paris-Guest-Whitelist
```