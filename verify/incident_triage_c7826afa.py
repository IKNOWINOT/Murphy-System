'''Verification file for incident #inc_c7826afa - Capacity info: No inbound replies in 999 days'''

# Check CRM activities API availability
try:
    import requests
    response = requests.get('http://localhost:8000/api/crm/activities?limit=10')
    print(f"CRM API response status: {response.status_code}")
    if response.status_code == 200:
        activities = response.json()
        print(f"Retrieved {len(activities.get('activities', []))} activities")
except Exception as e:
    print(f"Error accessing CRM API: {e}")

# Check server process status
import subprocess
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
print(f"Uvicorn process running: {'uvicorn' in result.stdout}")
