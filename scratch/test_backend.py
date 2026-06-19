import sys
import os
import traceback

sys.path.insert(0, os.path.abspath('.'))

def test_endpoints():
    try:
        from app.server import app
    except Exception as e:
        print("Failed to import app.server:")
        traceback.print_exc()
        sys.exit(1)

    app.config['TESTING'] = True
    app.config['PROPAGATE_EXCEPTIONS'] = True
    client = app.test_client()

    endpoints = [
        '/',
        '/compare',
        '/api/stock/AAPL',
        '/excel/AAPL'
    ]

    failed_endpoints = []

    for endpoint in endpoints:
        print(f"====================\nTesting {endpoint} ...")
        try:
            response = client.get(endpoint)
            print(f"Response status: {response.status_code}")
            if response.status_code >= 500:
                print(f"{response.status_code} Error for {endpoint}")
                failed_endpoints.append(endpoint)
        except Exception as e:
            print(f"Exception while testing {endpoint}:")
            traceback.print_exc()
            failed_endpoints.append(endpoint)
    
    if failed_endpoints:
        print("\nFailed endpoints:")
        for ep in failed_endpoints:
            print(f"- {ep}")
    else:
        print("\nNo 500 errors or exceptions encountered.")

if __name__ == "__main__":
    test_endpoints()
