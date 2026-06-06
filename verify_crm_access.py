import requests
import subprocess

def verify():
    # Check server process
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    server_running = 'uvicorn' in result.stdout
    
    # Check CRM activities endpoint
    try:
        response = requests.get('http://localhost:8000/api/crm/activities?limit=5')
        crm_data = response.json()
    except Exception as e:
        crm_data = str(e)
    
    return {'server_running': server_running, 'crm_data': crm_data}

if __name__ == '__main__':
    print(verify())