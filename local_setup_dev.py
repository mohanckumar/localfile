  
import subprocess
import json
import threading
import time
import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration
current_dir = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(current_dir, "output.json")
TUNNELITE_PATH = os.path.expanduser("~/Downloads/tunnelite.client.exe")  # Path to tunnelite.client.exe

# --------------------------- FLASK ENDPOINTS -------------------------------- #

@app.route('/fetch_client_url', methods=['GET'])
def fetch_client_url():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as file:
            data = json.load(file)
        urls = data.get("urls")
        if urls:
            return jsonify(urls), 200
        else:
            return "urls not found in the file", 400
    else:
        return "File not found", 404

@app.route('/openDesktopApp', methods=['POST'])
def openDesktopApp():
    try:
        data = request.get_json()
        if not data or 'AppPath' not in data:
            return jsonify({"error": "Missing or invalid 'AppPath' in the request body"}), 400
        app_path = data['AppPath']
        if not os.path.exists(app_path):
            return jsonify({"error": f"The file at '{app_path}' does not exist"}), 400    
        subprocess.Popen(app_path)
        return jsonify({"message": f"Application at '{app_path}' opened successfully"}), 200
    except FileNotFoundError as e:
        return jsonify({"error": f"File not found: {str(e)}"}), 404
    except PermissionError as e:
        return jsonify({"error": f"Permission denied: {str(e)}"}), 403
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# ---------------------- TUNNELITE MONITOR FUNCTIONALITY --------------------------- #

def write_public_urls_to_file(mobile_url, web_url, local_agent_url):
    """
    Write the public URLs to the output.json file.
    """
    try:
        data = {
            "urls": {
                "mobile_url": mobile_url,
                "web_url": web_url,
                "localagent_url": local_agent_url
            }
        }
        with open(OUTPUT_FILE, "w") as file:
            json.dump(data, file, indent=4)
        print(f"[INFO] URLs written to {OUTPUT_FILE}: {data['urls']}")
    except Exception as e:
        print(f"[ERROR] Failed to write URLs to file: {e}")

def monitor_tunnelite_process(port, temp_file):
    """
    Start tunnelite.client.exe and redirect output to a temp file.
    """
    try:
        print(f"[INFO] Starting tunnelite.client.exe for port {port}")
        command = f'cmd /k "{TUNNELITE_PATH} http://localhost:{port} --publicUrl http://tunneling.pearlarc.com > {temp_file} 2>&1"'
        process = subprocess.Popen(command, shell=True)
        print(f"[INFO] Started tunnelite.client.exe for port {port} (PID: {process.pid})")
        return process  # Return process object to keep it alive
    except Exception as e:
        print(f"[ERROR] Failed to start tunnelite for port {port}: {e}")
        return None

def extract_public_url(file_path):
    """
    Extract the public URL from the temp file content.
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
            match = re.search(r'http://\S+\.tunneling\.pearlarc\.com', content)
            return match.group(0) if match else None
        return None
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path}: {e}")
        return None

def monitor_tunnelite():
    """
    Monitor the tunnelite processes for each port and write URLs to file.
    """
    ports = {
        "4723": "temp1.txt",
        "4444": "temp2.txt",
        "5123": "temp3.txt"
    }
    processes = {}

    # Start tunnelite processes
    for port, temp_file in ports.items():
        processes[port] = monitor_tunnelite_process(port, temp_file)

    # Monitor temp files for URLs
    mobile_url, web_url, local_agent_url = None, None, None
    while not (mobile_url and web_url and local_agent_url):
        time.sleep(1)
        if not mobile_url and os.path.exists(ports["4723"]):
            mobile_url = extract_public_url(ports["4723"])
        if not web_url and os.path.exists(ports["4444"]):
            web_url = extract_public_url(ports["4444"])
        if not local_agent_url and os.path.exists(ports["5123"]):
            local_agent_url = extract_public_url(ports["5123"])
        if mobile_url and web_url and local_agent_url:
            write_public_urls_to_file(mobile_url, web_url, local_agent_url)
            # Clean up temp files
            for temp_file in ports.values():
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            break
            
@app.route('/getPublicUrl', methods=['GET'])
def getPublicUrl():
    port = request.args.get('port')
    # Correct the string formatting in address to use the actual `port` variable
    address = f"80:127.0.0.1:{port}"
 
    ssh_command1 = [
        "ssh", "-R", address, 
        "-o", "StrictHostKeyChecking=no", 
        "-o", "UserKnownHostsFile=/dev/null", 
        "nokey@localhost.run"
    ]
    process1 = subprocess.Popen(
        ssh_command1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0
    )
    print("output", process1.stdout.readline)
    public_url = None
    # Iterate over the output of the SSH command
    for line in iter(process1.stdout.readline, ""):
        # Assuming extract_url is a function that processes the output to get the URL
        print("line",line)
        public_url = extract_url(line)
        if public_url:
            break  # Return the first URL found and stop the iteration
    if not public_url:
        return jsonify({"error": "Failed to retrieve public URL"}), 500
    # Step 3: Fetch WebSocket Debugger URL from Chrome DevTools API
    try:
        response = requests.get(f"http://localhost:{port}/json/version")
        response_data = response.json()
        debugger_url = response_data.get("webSocketDebuggerUrl")
        if not debugger_url:
            return jsonify({"error": "No WebSocket Debugger URL found"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to fetch WebSocket URL: {str(e)}"}), 500
 
    print("Original WebSocket Debugger URL:", debugger_url)
 
    # Step 4: Replace "localhost" in WebSocket URL with the public IP
    modified_url = debugger_url.replace(f"localhost:{port}", public_url.replace("https://", "").replace("http://", ""))
    return jsonify({"debuggerUrl": modified_url}), 200

    # Keep processes running (no explicit termination)

# ---------------------------- MAIN FUNCTION -------------------------------- #

if __name__ == '__main__':
    # Start tunnelite monitoring in a separate thread
    tunnelite_thread = threading.Thread(target=monitor_tunnelite, daemon=True)
    tunnelite_thread.start()

    # Start Flask server
    app.run(host='0.0.0.0', port=5123)
