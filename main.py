from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "TNPSC PhotoBot is Running!"  # THIS MUST BE HERE

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Important!
    app.run(host='0.0.0.0', port=port)
