
import requests

url = "https://cmr.earthdata.nasa.gov/search/granules.json"

params = {
    "short_name": "MOD13Q1",
    "version": "061",
    "bounding_box": "-0.10,52.65,0.35,52.76",
    "temporal[]": (
        "2025-03-01T00:00:00Z,"
        "2025-10-31T23:59:59Z"
    ),
    "page_size": 10,
}

print("Testing NASA CMR directly...\n")

try:
    response = requests.get(
        url,
        params=params,
        headers={"Accept": "application/json"},
        timeout=60,
    )

    print("HTTP Status:", response.status_code)
    print("Request URL:", response.url)
    print("\nResponse:")

    print(response.text[:4000])

    response.raise_for_status()

    data = response.json()

    print("\nTotal matching granules:", data.get("hits"))

except requests.RequestException as error:
    print("\nRequest failed:", error)
