# Used a flask to run multiple instances / threads of the streamlit app

from flask import Flask , redirect , url_for
import subprocess
import threading

app = Flask(__name__)

@app.route('/start_streamlit')
def start_streamlit():
    def run_streamlit():
        subprocess.run(["streamlit", "run", "main_AK.py"])
    
    threading.Thread(target=run_streamlit).start()
    return "Streamlit app started!"

@app.route('/')
def home():
    return redirect(url_for('start_streamlit'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
