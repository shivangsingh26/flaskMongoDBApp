from flask import Flask, request, jsonify

app = Flask(__name__)

data = {}

#GET METHOD -- to fetch value from dictionary using a key
@app.route('/item/<string:key>', methods=['GET'])
def get_item(key):
    return jsonify({key: data.get(key, "Not Found")}), 200 #200 is reques succeeded message

#POST METHOD -- add new key-value pair(item) to dictionary
@app.route('/item', methods=['POST'])
def add_item():
    item = request.json
    data.update(item)
    return jsonify(item), 201 #new resource created so using 201

#PUT METHOD -- replace value of existing key
@app.route('/item/<string:key>', methods=['PUT'])
def update_item(key):
    item = request.json
    data[key] = item.get(key)
    return jsonify({key: data[key]}), 200

#PATCH METHOD -- update value of existing key
@app.route('/item/<string:key>', methods=['PATCH'])
def modify_item(key): 
    updates = request.json
    if key in data:
        data[key] = updates
    
    return jsonify({key: data.get(key)}), 200

@app.route('/item/<string:key>', methods = ['DELETE'])
def delete_item(key):
    removed_item = data.pop(key, None)
    return jsonify({"removed": removed_item}), 200 if removed_item else 404

if __name__ == '__main__':
    app.run(debug=True)