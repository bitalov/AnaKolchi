# Used a flask to run multiple instances / threads of the streamlit app

from flask import Flask , redirect , url_for
import subprocess
import threading
import socket

app = Flask(__name__)

def find_free_port(start_port=8501):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                port += 1

@app.route('/start_streamlit')

def start_streamlit():
    port = find_free_port()

    def run_streamlit():
        # Run Streamlit in the background
        subprocess.Popen(["streamlit", "run", "main_AK.py", "--server.port={}".format(port)])
    
    threading.Thread(target=run_streamlit).start()

    # Replace '51.20.35.85' with your EC2 instance's IP address
    return redirect(f"http://51.20.35.85:{port}", code=302)

    #local no need
    #return "Streamlit app started !"

@app.route('/')
def home():
    return redirect(url_for('start_streamlit'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
