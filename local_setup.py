from flask import Flask, request, jsonify
import os
import subprocess
import re
import json
import threading
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  

# Configuration
VALID_API_KEY = "5617c952-169c-4bf7-a92f-2600593f7c11"
current_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory where the script is executing
OUTPUT_FILE = os.path.join(current_dir, "output.txt")     # Path to output.txt

# --------------------------- FLASK ENDPOINTS -------------------------------- #


# Endpoint 1: Fetch Client URL from the File
@app.route('/fetch_client_url', methods=['GET'])
def fetch_client_url():
    # Uncomment and modify the authorization check as needed
    # api_key = request.headers.get('Authorization')
    # if api_key is None:
    #     return jsonify({"error": "API key is missing"}), 400
    
    # if api_key != f"Bearer {VALID_API_KEY}":
    #     return jsonify({"error": "Invalid API key"}), 403

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as file:
            data = json.load(file)  # Load the JSON data from the file
        url_is = data.get("UrlIs")  # Extract the value of "UrlIs"
        
        if url_is:
            return url_is, 200  # Return the value of UrlIs as a plain string
        else:
            return "UrlIs not found in the file", 400
    else:
        return "File not found", 404
@app.route('/openDesktopApp', methods=['POST'])
def openDesktopApp():
    #api_key = request.headers.get('Authorization')
    #data = request.get_json()
    #app_path = data['AppPath']
    #if api_key is None:
    #    return jsonify({"error": "API key is missing"}), 400
    
    #if api_key != f"Bearer {VALID_API_KEY}":
    #    return jsonify({"error": "Invalid API key"}), 403
    
    subprocess.Popen(app_path)
    return "", 200

@app.route('/fetch_hello', methods=['GET'])
def fetch_hello():
    return "hi", 200

# ---------------------- SSH MONITOR FUNCTIONALITY --------------------------- #

# Function to extract the URL after "tunneled with tls termination,"
def extract_url(line):
    match = re.search(r"tunneled with tls termination, (https?://[^\s]+)", line)
    return match.group(1) if match else None

# Function to write the new URL to the output file
def write_url_to_file(url):
    data = {"UrlIs": url}
    with open(OUTPUT_FILE, "w") as file:
        file.write(json.dumps(data))
    print(f"URL updated: {url}")

# Function to run the SSH command and monitor its output
def monitor_ssh():
    #ssh_command = ["ssh", "-R", "4444:localhost:4444", "-R", "80:localhost:5000", "nokey@localhost.run"]
    ssh_command = ["ssh", "-R", "80:localhost:4444", "nokey@localhost.run"]
    print("Running SSH command...")
    process = subprocess.Popen(
        ssh_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    seen_url = None
    try:
        for line in iter(process.stdout.readline, ""):
            url = extract_url(line)
            if url and url != seen_url:
                seen_url = url
                write_url_to_file(url)
    except KeyboardInterrupt:
        print("\nProcess interrupted. Exiting...")
    finally:
        process.terminate()

# ---------------------------- MAIN FUNCTION -------------------------------- #

if __name__ == '__main__':
    # Start SSH monitoring in a separate thread
    ssh_thread = threading.Thread(target=monitor_ssh, daemon=True)
    ssh_thread.start()

    # Start Flask server
    app.run(host='0.0.0.0', port=5123)
