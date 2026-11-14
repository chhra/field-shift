
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests
import earthaccess


# -----------------------------------------
# 1. Farm reference coordinates
# -----------------------------------------

LATITUDE = 52.7045524
LONGITUDE = 0.2431611

START_DATE = "2025-03-01T00:00:00Z"
END_DATE = "2025-10-31T23:59:59Z"


# -----------------------------------------
# 2. Authenticate with Earthdata
# -----------------------------------------

print("Connecting to NASA Earthdata...")

try:
    earthaccess.login(strategy="interactive")
    download_session = earthaccess.get_requests_https_session()

    print("Earthdata authentication successful!")

except Exception as error:
    raise SystemExit(f"Authentication failed: {error}")


# -----------------------------------------
# 3. Search NASA CMR directly
# -----------------------------------------

CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"

params = {
    "short_name": "MOD13Q1",
    "version": "061",
    "point": f"{LONGITUDE},{LATITUDE}",
    "temporal[]": f"{START_DATE},{END_DATE}",
    "page_size": 20,
}

print("\nSearching MODIS for Peartree Farm...")

try:
    response = requests.get(
        CMR_URL,
        params=params,
        headers={"Accept": "application/json"},
        timeout=60,
    )

    response.raise_for_status()
    data = response.json()

except requests.RequestException as error:
    raise SystemExit(f"CMR search failed: {error}")


entries = data.get("feed", {}).get("entry", [])

print(f"Results returned: {len(entries)}")
print(f"CMR total hits: {response.headers.get('CMR-Hits', 'Unknown')}")


if not entries:
    raise SystemExit("No MODIS granules found for this location.")


# -----------------------------------------
# 4. Find downloadable HDF granule
# -----------------------------------------

selected_entry = None
download_url = None

DATA_RELATION = "http://esipfed.org/ns/fedsearch/1.1/data#"

for entry in entries:

    links = entry.get("links", [])

    for link in links:

        href = link.get("href", "")

        if (
            link.get("rel") == DATA_RELATION
            and href.lower().endswith(".hdf")
        ):
            selected_entry = entry
            download_url = href
            break

    if download_url:
        break


if not download_url:
    raise SystemExit(
        "No downloadable HDF link was found in the CMR results."
    )


print("\nSelected granule:")
print(selected_entry.get("producer_granule_id"))

print("Acquisition period:")
print(selected_entry.get("time_start"))
print(selected_entry.get("time_end"))

print("File size reported by CMR:")
print(selected_entry.get("granule_size"), "MB")


# -----------------------------------------
# 5. Download one HDF file
# -----------------------------------------

output_dir = Path("data/raw/modis_sample")
output_dir.mkdir(parents=True, exist_ok=True)

filename = unquote(
    Path(urlparse(download_url).path).name
)

output_file = output_dir / filename

if output_file.exists() and output_file.stat().st_size > 0:

    print(f"\nFile already exists: {output_file}")

else:

    print("\nDownloading MODIS HDF...")

    try:
        with download_session.get(
            download_url,
            stream=True,
            timeout=(30, 300),
        ) as download_response:

            download_response.raise_for_status()

            total_bytes = 0

            with open(output_file, "wb") as file:

                for chunk in download_response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)
                        total_bytes += len(chunk)

        if total_bytes == 0:
            output_file.unlink(missing_ok=True)
            raise SystemExit("Downloaded file is empty.")

        print("Download successful!")
        print(f"Downloaded size: {total_bytes / (1024**2):.2f} MB")

    except Exception as error:

        output_file.unlink(missing_ok=True)

        raise SystemExit(f"Download failed: {error}")


# -----------------------------------------
# 6. Final verification
# -----------------------------------------

print("\nMODIS sample ready!")
print(f"Location: {output_file.resolve()}")
print(f"Size: {output_file.stat().st_size / (1024**2):.2f} MB")



































# from pathlib import Path

# import earthaccess


# # -----------------------------------------
# # 1. Authenticate using Earthdata Token
# # -----------------------------------------

# print("Connecting to NASA Earthdata...")

# try:
#     auth = earthaccess.login(strategy="environment")
#     print("Earthdata authentication successful!")

# except Exception as error:
#     raise SystemExit(
#         f"Earthdata authentication failed: {error}"
#     )


# # -----------------------------------------
# # 2. Peartree Farm reference location
# # -----------------------------------------

# LATITUDE = 52.7045524
# LONGITUDE = 0.2431611

# # Bounding box:
# # (West, South, East, North)

# BBOX = (
#     -0.10,
#     52.65,
#     0.35,
#     52.76
# )


# # -----------------------------------------
# # 3. Search MODIS dataset
# # -----------------------------------------

# print("\nSearching MODIS MOD13Q1.061...")

# results = earthaccess.search_data(
#     short_name="MOD13Q1",
#     version="061",
#     bounding_box=BBOX,
#     temporal=("2025-03-01", "2025-10-31"),
#     count=100
# )

# print(f"\nMatching granules: {len(results)}")


# if not results:
#     raise SystemExit(
#         "No granules found. Check the product and search region."
#     )


# # -----------------------------------------
# # 4. Display some available files
# # -----------------------------------------

# print("\nFirst matching granules:")

# for index, granule in enumerate(results[:5], start=1):

#     metadata = granule.get("umm", {})

#     name = metadata.get(
#         "GranuleUR",
#         "Granule name unavailable"
#     )

#     print(f"{index}. {name}")


# # -----------------------------------------
# # 5. Download one sample granule
# # -----------------------------------------

# output_dir = Path("data/raw/modis_sample")
# output_dir.mkdir(parents=True, exist_ok=True)

# print("\nDownloading one sample granule...")

# try:
#     downloaded_files = earthaccess.download(
#         [results[0]],
#         local_path=str(output_dir)
#     )

# except Exception as error:
#     raise SystemExit(
#         f"MODIS download failed: {error}"
#     )


# # -----------------------------------------
# # 6. Display downloaded file
# # -----------------------------------------

# print("\nDownload completed!")

# for file_path in downloaded_files:
#     print(file_path)
