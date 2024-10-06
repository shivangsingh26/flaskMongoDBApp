from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import redis
import json

app = Flask(__name__)

#MONGODB SETUP
app.config["MONGO_URI"] = "mongodb://localhost:27017/lincodeDB"
lincodeDB = PyMongo(app).db

#MONGODB COLLECTION Instance
lincodeCollection = lincodeDB.lincodeCollection

#Setup Redis Connection
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

#Function to cache data in Redis
def cache_data(key, data, expiry=300):
    redis_client.setex(key, expiry, json.dumps(data))

# Function to retrieve cached data from Redis
def get_cached_data(key):
    cached_data = redis_client.get(key)
    if cached_data:
        return json.loads(cached_data)
    return None

@app.route('/', methods=['GET'])
def root():
    return jsonify({"message": "Server is running"})

#GET METHOD - TO RETRIEVE ALL USERS
@app.route('/users', methods=['GET'])
def get_all_users():
    # Check cache first
    cached_users = get_cached_data('all_users')
    if cached_users:
        return jsonify(cached_users)

    # If not in cache, get from MongoDB
    users = list(lincodeCollection.find())
    for user in users:
        user["_id"] = str(user["_id"])
    
    # Cache the results
    cache_data('all_users', users)
    
    return jsonify(users)

#GET METHOD - TO RETRIEVE SINGLE USER
@app.route('/users/<string:user_id>', methods=['GET'])
def get_user(user_id):
    # Check cache first
    cached_user = get_cached_data(f"user:{user_id}")
    if cached_user:
        return jsonify(cached_user)

    # If not in cache, get from MongoDB
    user = lincodeCollection.find_one({"_id": ObjectId(user_id)})
    if user:
        user["_id"] = str(user["_id"])
        # Cache the user data
        cache_data(f"user:{user_id}", user)
        return jsonify(user)

    return jsonify({"error": "User not found"}), 404

#POST METHOD - TO ADD NEW USER
@app.route('/users', methods=['POST'])
def create_user():
    data = request.json
    result = lincodeCollection.insert_one(data)
    
    # Invalidate the all_users cache
    redis_client.delete('all_users')
    
    # Cache the new user
    new_user = {**data, "_id": str(result.inserted_id)}
    cache_data(f"user:{str(result.inserted_id)}", new_user)
    
    return jsonify({"message": "User created successfully", "id": str(result.inserted_id)}), 201

#PUT METHOD - TO UPDATE USER
@app.route('/users/<string:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    data['_id'] = ObjectId(user_id)
    result = lincodeCollection.replace_one({"_id": ObjectId(user_id)}, data)

    if result.modified_count > 0:
        # Invalidate caches
        redis_client.delete(f"user:{user_id}")
        redis_client.delete('all_users')
        
        # Update cache with new data
        updated_user = {**data, "_id": user_id}
        cache_data(f"user:{user_id}", updated_user)
        
        return jsonify({"message": "User updated successfully"}), 200
    return jsonify({"error": "User not found"}), 404

#PATCH METHOD - TO PARTIALLY UPDATE USER
@app.route('/users/<string:user_id>', methods=['PATCH'])
def patch_user(user_id):
    data = request.json
    
    # First, get the existing user (try cache first, then MongoDB)
    existing_user = get_cached_data(f"user:{user_id}")
    if not existing_user:
        existing_user = lincodeCollection.find_one({"_id": ObjectId(user_id)})
        if existing_user:
            existing_user["_id"] = str(existing_user["_id"])
    
    if not existing_user:
        return jsonify({"error": "User not found"}), 404
    
    # Update MongoDB
    result = lincodeCollection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": data}
    )

    if result.modified_count > 0:
        # Update the existing user data with the patched data
        updated_user = {**existing_user, **data}
        
        # Invalidate and update caches
        redis_client.delete('all_users')  # Invalidate the all_users cache
        cache_data(f"user:{user_id}", updated_user)  # Update user cache
        
        return jsonify({
            "message": "User patched successfully",
            "user": updated_user
        }), 200
    
    return jsonify({"message": "No changes applied"}), 200

#DELETE METHOD - TO DELETE USER
@app.route('/users/<string:user_id>', methods=['DELETE'])
def delete_user(user_id):
    result = lincodeCollection.delete_one({"_id": ObjectId(user_id)})

    if result.deleted_count > 0:
        # Invalidate caches
        redis_client.delete(f"user:{user_id}")
        redis_client.delete('all_users')
        
        return jsonify({"message": "User deleted successfully"})
    
    return jsonify({"error": "User not found"}), 404

# BULK POST METHOD - To add multiple users
@app.route('/users/bulk', methods=['POST'])
def bulk_create_users():
    data = request.json

    if isinstance(data, list):
        result = lincodeCollection.insert_many(data)
        inserted_ids = [str(_id) for _id in result.inserted_ids]
        
        # Invalidate all_users cache
        redis_client.delete('all_users')
        
        # Cache each new user
        for i, user_data in enumerate(data):
            new_user = {**user_data, "_id": inserted_ids[i]}
            cache_data(f"user:{inserted_ids[i]}", new_user)
        
        return jsonify({
            "message": "Users created successfully",
            "inserted_ids": inserted_ids
        }), 201
    else:
        return jsonify({"error": "Input data should be a list of JSON objects"}), 400

if __name__ == "__main__":
    app.run(debug=True)