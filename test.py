from flask import Flask
from flask_pymongo import PyMongo

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://localhost:27017/lincodeDB"
db = PyMongo(app).db

@app.route('/')
def add_name():
    db.lincodeCollection.insert_one({"name2": "John"})
    return 'name added'

app.run(debug=True)