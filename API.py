from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import redis
import json
import os

app = Flask(__name__)

# MongoDB setup
url = "mongodb://localhost:27017/lincodeDB"
# url = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/lincodeDB')
mongo_client = MongoClient(url)
db = mongo_client["lincodeDB"]
collection = db["lincodeCollection"]


def check_mongodb_connection():
    try:
        mongo_client.admin.command('ping')
        print("MongoDB connection successful")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")

check_mongodb_connection()

# Redis setup
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)


def check_redis_connection():
    try:
        redis_client.ping()
        print("Redis connection successful")
    except Exception as e:
        print(f"Redis connection failed: {e}")

check_redis_connection()


def get_data_from_db(document_id):
    return collection.find_one({"_id": ObjectId(document_id)})


def cache_data(document_id, data):
    redis_client.setex(f"document:{document_id}", 300, json.dumps(data))

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "message": "Welcome to the LinCode API",
        "version": "1.0",
        "endpoints": [
            {"method": "GET", "path": "/data", "description": "Fetch all data"},
            {"method": "GET", "path": "/data/<document_id>", "description": "Fetch data by id"},
            {"method": "POST", "path": "/data", "description": "Create new data"},
            {"method": "PUT", "path": "/data/<document_id>", "description": "Update data completely"},
            {"method": "PATCH", "path": "/data/<document_id>", "description": "Partially update data"},
            {"method": "DELETE", "path": "/data/<document_id>", "description": "Delete data"},
            {"method": "POST", "path": "/cache/flush", "description": "Flush Redis cache"},
            {"method": "GET", "path": "/cache/data", "description": "View all cached data"}
        ]
    })



# Fetch all data
@app.route('/data', methods=['GET'])
def get_all_data():
    data = list(collection.find({}))
    for item in data:
        item["_id"] = str(item["_id"])
    return jsonify(data)


# Fetch data by id
@app.route('/data/<string:document_id>', methods=['GET'])
def get_data(document_id):
    # Try to get the data from Redis cache
    cached_data = redis_client.get(f"document:{document_id}")
    if cached_data:
        return jsonify(json.loads(cached_data))

    # If not found in cache, fetch from MongoDB
    data = get_data_from_db(document_id)
    if data:
        data["_id"] = str(data["_id"])
        # Cache the data in Redis
        cache_data(document_id, data)
        return jsonify(data)
    else:
        return jsonify({"error": "Data not found"}), 404

# Create new data
@app.route('/data', methods=['POST'])
def create_data():
    data = request.get_json()

    # Insert data into MongoDB
    result = collection.insert_one(data)
    document_id = str(result.inserted_id)

    # Cache the newly created data
    data["_id"] = document_id
    cache_data(document_id, data)

    return jsonify({"message": "Data created", "id": document_id}), 201

# Update data completely by id
@app.route('/data/<string:document_id>', methods=['PUT'])
def update_data(document_id):
    data = request.get_json()

    # Update the document in MongoDB
    result = collection.update_one({"_id": ObjectId(document_id)}, {"$set": data})

    if result.modified_count > 0:
        # Update the cache
        data["_id"] = document_id
        cache_data(document_id, data)
        return jsonify({"message": "Data updated"})
    else:
        return jsonify({"error": "Data not found"}), 404

# Partially update data by id
@app.route('/data/<string:document_id>', methods=['PATCH'])
def patch_data(document_id):
    data = request.get_json()

    # Partially update the document in MongoDB
    result = collection.update_one({"_id": ObjectId(document_id)}, {"$set": data})

    if result.modified_count > 0:
        # Update the cache
        updated_data = get_data_from_db(document_id)
        updated_data["_id"] = str(updated_data["_id"])
        cache_data(document_id, updated_data)
        return jsonify({"message": "Data patched"})
    else:
        return jsonify({"error": "Data not found"}), 404

# Delete data by id
@app.route('/data/<string:document_id>', methods=['DELETE'])
def delete_data(document_id):
    result = collection.delete_one({"_id": ObjectId(document_id)})

    if result.deleted_count > 0:
        # Remove the data from cache
        redis_client.delete(f"document:{document_id}")
        return jsonify({"message": "Data deleted"})
    else:
        return jsonify({"error": "Data not found"}), 404
    
    

# Flush Redis cache
@app.route('/cache/flush', methods=['POST'])
def flush_cache():
    try:
        redis_client.flushdb()
        return jsonify({"message": "Redis cache flushed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# View all cached data
@app.route('/cache/data', methods=['GET'])
def view_cache_data():
    try:
        keys = redis_client.keys('document:*')
        cached_data = {}
        for key in keys:
            cached_data[key] = json.loads(redis_client.get(key))
        return jsonify(cached_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    

if __name__ == '__main__':
    app.run(debug=True)
