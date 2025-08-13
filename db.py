from flask import Flask, jsonify, request
from flask_cors import CORS
import datetime
from bson.objectid import ObjectId
from db import foodPosted, foodConfirmed  # Your existing Mongo collections

app = Flask(__name__)
CORS(app)

@app.route('/api/foodPosted', methods=['GET'])
def get_food_posted():
    # Only unclaimed food posts
    data = list(foodPosted.find({'claimed': False}, {
        '_id': 1, 'type': 1, 'description': 1, 'quantity': 1, 'useBy': 1,
        'address': 1, 'contact': 1, 'image': 1
    }))
    # Convert _id to string and format date
    for item in data:
        item['id'] = str(item['_id'])
        del item['_id']
        item['useBy'] = item['useBy'].strftime('%Y-%m-%d') if 'useBy' in item else ''
    return jsonify(data)

@app.route('/api/foodConfirmed', methods=['GET'])
def get_food_confirmed():
    data = list(foodConfirmed.find({}, {'_id': 0}))
    return jsonify(data)

@app.route('/api/foodPosted', methods=['POST'])
def add_food_posted():
    data = request.get_json()
    required_fields = ['type', 'description', 'quantity', 'useBy', 'address', 'contact', 'image']
    if not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing fields'}), 400

    try:
        use_by_date = datetime.datetime.strptime(data['useBy'], '%Y-%m-%d')
    except ValueError:
        return jsonify({'message': 'Invalid useBy date format'}), 400

    new_food = {
        'type': data['type'],
        'description': data['description'],
        'quantity': data['quantity'],
        'useBy': use_by_date,
        'address': data['address'],
        'contact': data['contact'],
        'image': data['image'],  # base64 string from frontend
        'createdAt': datetime.datetime.utcnow(),
        'claimed': False  # default unclaimed
    }

    result = foodPosted.insert_one(new_food)
    return jsonify({'message': 'Food posted saved', 'id': str(result.inserted_id)}), 201

@app.route('/api/foodPosted/claim/<food_id>', methods=['POST'])
def claim_food(food_id):
    try:
        result = foodPosted.update_one(
            {'_id': ObjectId(food_id), 'claimed': False},
            {'$set': {'claimed': True}}
        )
        if result.modified_count == 0:
            return jsonify({'message': 'Food already claimed or not found'}), 404
        return jsonify({'message': 'Food claimed successfully'})
    except Exception:
        return jsonify({'message': 'Invalid food id'}), 400

if __name__ == '__main__':
    app.run(debug=True)
