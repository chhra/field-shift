
import earthaccess

URL = (
    "https://data.lpdaac.earthdatacloud.nasa.gov/"
    "lp-prod-protected/MOD13Q1.061/"
    "MOD13Q1.A2025049.h18v03.061.2025070114722/"
    "MOD13Q1.A2025049.h18v03.061.2025070114722.hdf"
)

print("Logging in interactively...")

try:
    auth = earthaccess.login(strategy="interactive")

    print("\nLogin completed.")

    session = earthaccess.get_requests_https_session()

    print("Testing LP DAAC authorization...")

    response = session.get(
        URL,
        headers={"Range": "bytes=0-1023"},
        stream=True,
        allow_redirects=True,
        timeout=60
    )

    print("HTTP status:", response.status_code)
    print("Final URL:", response.url)

    if response.status_code in (200, 206):
        print("\nSUCCESS: LP DAAC access is working!")

    else:
        print("\nAccess is still failing.")
        print(response.text[:1000])

    response.close()

except Exception as error:
    print("\nAuthentication test failed:")
    print(type(error).__name__, error)
