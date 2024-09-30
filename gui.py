from flask import Flask, render_template
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
