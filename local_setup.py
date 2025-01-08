from flask import Flask, request, jsonify
import os, subprocess, re, json, threading, time, requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  

# Configuration
current_dir = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(current_dir, "output.json")

# --------------------------- FLASK ENDPOINTS -------------------------------- #

# Endpoint 1: Fetch Client URL from the File
@app.route('/fetch_client_url', methods=['GET'])
def fetch_client_url():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as file:
            data = json.load(file)  # Load the JSON data from the file
        urls = data.get("urls")  # Extract the value of "UrlIs"
        
        if urls:
            return urls, 200  # Return the value of UrlIs as a plain string
        else:
            return "UrlIs not found in the file", 400
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

    
# ---------------------- SSH MONITOR FUNCTIONALITY --------------------------- #

def ping_urls():
    interval = 600  # Ping every 5 minutes
    while True:
        try:
            if os.path.exists(OUTPUT_FILE):
                with open(OUTPUT_FILE, "r") as file:
                    data = json.load(file)
                urls = data.get("urls", {})
                for url_key, url in urls.items():
                    try:
                        if url_key == "mobile_url":
                            response = requests.get(f'{url}/wd/hub/sessions')
                        elif url_key == "web_url":
                            response = requests.get(f'{url}/status')
                        print(f"Pinged {url_key} ({url}) successfully. Status code: {response.status_code}")
                    except Exception as e:
                        print(f"Failed to ping {url_key} ({url}): {e}")
            else:
                print(f"{OUTPUT_FILE} not found.")
        except Exception as e:
            print(f"An error occurred in ping_urls: {e}")
        time.sleep(interval)
        
# Function to extract the URL after "tunneled with tls termination,"
def extract_url(line):
    match = re.search(r"tunneled with tls termination, (https?://[^\s]+)", line)
    return match.group(1) if match else None

def write_urls_to_file(seen_urls):
    urls_data = {
        "urls": {
            "dsktop_url": seen_urls.get("80"),
            "web_url": seen_urls.get("8080"),
            "mobile_url": seen_urls.get("8081")
        }
    }
    # Write both URLs to the output file in JSON format
    with open(OUTPUT_FILE, "w") as file:
        json.dump(urls_data, file, indent=4)
    print("[INFO] URLs written to file:", urls_data)

def monitor_process(process, port_key, seen_urls, lock):
    # Monitor a single SSH process for URLs
    for line in iter(process.stdout.readline, ""):
        print(f"Output from port {port_key}: {line.strip()}")  # Debugging: Print raw output
        url = extract_url(line)
        if url:
            with lock:
                if seen_urls.get(port_key) != url:
                    seen_urls[port_key] = url
                    write_urls_to_file(seen_urls)
                    print(f"URL for port {port_key}: {url}")
    process.stdout.close()

def monitor_ssh():
    ssh_command1 = ["ssh", "-R", "80:127.0.0.1:5123", "nokey@localhost.run"]
    ssh_command2 = ["ssh", "-R", "80:127.0.0.1:4444", "nokey@localhost.run"]
    ssh_command3 = ["ssh", "-R", "80:127.0.0.1:4723", "nokey@localhost.run"]

    print("Running SSH commands...")

    # Start SSH processes
    process1 = subprocess.Popen(
        ssh_command1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0
    )
    process2 = subprocess.Popen(
        ssh_command2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0
    )
    process3 = subprocess.Popen(
        ssh_command3, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0
    )

    # Shared data to store URLs
    seen_urls = {}
    lock = threading.Lock()

    # Monitor processes in separate threads
    thread1 = threading.Thread(target=monitor_process, args=(process1, "80", seen_urls, lock))
    thread2 = threading.Thread(target=monitor_process, args=(process2, "8080", seen_urls, lock))
    thread3 = threading.Thread(target=monitor_process, args=(process3, "8081", seen_urls, lock))
    thread1.start()
    thread2.start()
    thread3.start()

    try:
        # Wait for threads to complete
        thread1.join()
        thread2.join()
        thread3.join()
    except KeyboardInterrupt:
        print("\nProcess interrupted. Exiting...")
    finally:
        process1.terminate()
        process2.terminate()
        process3.terminate()

# ---------------------------- MAIN FUNCTION -------------------------------- #

if __name__ == '__main__':
    # Start SSH monitoring in a separate thread
    ssh_thread = threading.Thread(target=monitor_ssh, daemon=True)
    ssh_thread.start()
    
    ping_thread = threading.Thread(target=ping_urls, daemon=True)
    ping_thread.start()

    # Start Flask server
    app.run(host='0.0.0.0', port=5123)
