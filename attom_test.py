import requests

API_KEY = "0b80ec6ea49566d23185cb62a5511b25"

headers = {
    "accept": "application/json",
    "apikey": API_KEY,
}

base = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"

# 1) Call Basic Profile
bp_params = {
    "address": "468 SEQUOIA DR, SMYRNA, DE 19977"  # use any test address you know is valid
}
bp_resp = requests.get(f"{base}/property/basicprofile", headers=headers, params=bp_params)
print("BASIC PROFILE STATUS:", bp_resp.status_code)
print(bp_resp.text[:2000])
bp_resp.raise_for_status()
bp_json = bp_resp.json()

# 2) Call Detail Owner
properties = bp_json.get("property", [])

if not properties:
    print("NO PROPERTY RETURNED FROM BASIC PROFILE")
    exit()

attom_id = properties[0].get("identifier", {}).get("attomId")

print("ATTOM ID:", attom_id)

do_params = {
    "attomId": attom_id
}

do_resp = requests.get(f"{base}/property/detailowner", headers=headers, params=do_params)
print("DETAIL OWNER STATUS:", do_resp.status_code)
print(do_resp.text[:2000])
do_resp.raise_for_status()
do_json = do_resp.json()

# 3) Optionally: recursively collect all JSON paths (field names)
def walk(prefix, obj, paths):
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(f"{prefix}.{k}" if prefix else k, v, paths)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(f"{prefix}[{i}]", v, paths)
    else:
        paths.add(prefix)

paths_basic = set()
paths_detailowner = set()
walk("", bp_json, paths_basic)
walk("", do_json, paths_detailowner)

print("BasicProfile fields:")
for p in sorted(paths_basic):
    print(p)

print("BASIC PROFILE STATUS:", bp_resp.status_code)
print(bp_resp.text[:2000])

print("\nDetailOwner fields:")
for p in sorted(paths_detailowner):
    print(p)

print("DETAIL OWNER STATUS:", do_resp.status_code)
print(do_resp.text[:2000])