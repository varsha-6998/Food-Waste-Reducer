from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from bson.objectid import ObjectId
from datetime import datetime
import time
from db import foodPosted, foodConfirmed, ngo_col  # Your Mongo collections

# ---------------------------
# Flask and SocketIO setup
# ---------------------------
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------------------------
# Ensure indexes
# ---------------------------
ngo_col.create_index([("location", "2dsphere")])


# ---------------------------
# API endpoints
# ---------------------------
@app.route('/api/foodPosted', methods=['GET'])
def get_food_posted():
    data = list(foodPosted.find({'claimed': False}, {
        '_id': 1, 'type': 1, 'description': 1, 'quantity': 1,
        'useBy': 1, 'address': 1, 'contact': 1, 'image': 1
    }))
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
        use_by_date = datetime.strptime(data['useBy'], '%Y-%m-%d')
    except ValueError:
        return jsonify({'message': 'Invalid useBy date format'}), 400

    new_food = {
        'type': data['type'],
        'description': data['description'],
        'quantity': data['quantity'],
        'useBy': use_by_date,
        'address': data['address'],
        'contact': data['contact'],
        'image': data['image'],
        'createdAt': datetime.utcnow(),
        'claimed': False
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

# ---------------------------
# Flask routes
# ---------------------------
@app.route("/")
def home():
    return render_template("map.html")

@app.route("/ngo")
def ngo_console():
    return render_template("ngo.html")

@app.route("/api/ngo/register", methods=["POST"])
def register_ngo():
    data = request.get_json()
    name = data.get("name")
    address = data.get("address")
    lat = float(data.get("lat", 0))
    lng = float(data.get("lng", 0))
    payload = {
        "name": name,
        "address": address,
        "location": {"type": "Point", "coordinates": [lng, lat]},
        "active": True,
        "updated_at": datetime.utcnow(),
        "created_at": datetime.utcnow(),
    }
    ngo_id = data.get("ngo_id")
    if ngo_id:
        ngo_col.update_one({"_id": ObjectId(ngo_id)}, {"$set": payload})
        doc = ngo_col.find_one({"_id": ObjectId(ngo_id)})
        return jsonify({"ok": True, "ngo": {"_id": str(doc["_id"]), "name": doc["name"]}})
    else:
        res = ngo_col.insert_one(payload)
        return jsonify({"ok": True, "ngo": {"_id": str(res.inserted_id), "name": name}})

# ---------------------------
# Helper functions
# ---------------------------
def find_next_ngos(donation, batch=3, radius_m=10000):
    lng, lat = donation["location"]["coordinates"]
    exclude = set(donation.get("notified_ngo_ids", []))
    query = {
        "active": True,
        "location": {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": radius_m,
            }
        },
    }
    out = []
    for ngo in ngo_col.find(query):
        sid = str(ngo["_id"])
        if sid not in exclude:
            out.append(ngo)
            if len(out) >= batch:
                break
    return out

def notify_batch(donation, ngos):
    ids = [str(n["_id"]) for n in ngos]
    donation_col.update_one(
        {"_id": donation["_id"], "status": "pending"},
        {"$addToSet": {"notified_ngo_ids": {"$each": ids}},
         "$inc": {"round": 1},
         "$set": {"updated_at": datetime.utcnow()}}
    )
    payload = {
        "type": "donation_available",
        "donation_id": str(donation["_id"]),
        "food": donation["food"],
        "donor_name": donation["donor_name"],
        "approx_area": donation["address"],
        "round": donation.get("round", 0) + 1,
    }
    for n in ngos:
        room = f"ngo:{str(n['_id'])}"
        socketio.emit("notify_donation", payload, room=room)

def notify_next_batches(donation_id):
    interval = 300  # 5 minutes
    while True:
        d = donation_col.find_one({"_id": ObjectId(donation_id)})
        if not d or d["status"] != "pending":
            return
        if d.get("expires_at") and datetime.utcnow() > d["expires_at"]:
            donation_col.update_one(
                {"_id": d["_id"]},
                {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}}
            )
            return
        ngos = find_next_ngos(d)
        if ngos:
            notify_batch(d, ngos)
        slept = 0
        while slept < interval:
            time.sleep(5)
            slept += 5
            cur = donation_col.find_one({"_id": d["_id"]})
            if cur["status"] != "pending":
                return

# ---------------------------
# SocketIO handlers
# ---------------------------
@socketio.on("register_ngo_socket")
def register_socket(data):
    ngo_id = data.get("ngo_id")
    if not ngo_id:
        return
    join_room(f"ngo:{ngo_id}")
    emit("socket_registered", {"ok": True})

@socketio.on("accept_donation")
def accept_donation(data):
    ngo_id = data["ngo_id"]
    donation_id = data["donation_id"]

    res = donation_col.update_one(
        {"_id": ObjectId(donation_id), "status": "pending"},
        {"$set": {"status": "assigned", "accepted_by": ngo_id, "updated_at": datetime.utcnow()}}
    )
    if res.modified_count == 0:
        emit("accept_result", {"ok": False, "reason": "Already assigned"})
        return

    d = donation_col.find_one({"_id": ObjectId(donation_id)})

    socketio.emit(
        "donation_assigned",
        {
            "donation_id": donation_id,
            "address": d["address"],
            "lat": d["location"]["coordinates"][1],
            "lng": d["location"]["coordinates"][0],
            "food": d["food"],
            "donor_name": d["donor_name"],
        },
        room=f"ngo:{ngo_id}",
    )

    for other in d.get("notified_ngo_ids", []):
        if other != ngo_id:
            socketio.emit(
                "donation_cleared", {"donation_id": donation_id, "status": "assigned"}, room=f"ngo:{other}"
            )
    emit("accept_result", {"ok": True})

# ---------------------------
# Run app
# ---------------------------
if __name__ == '__main__':
    socketio.run(app, debug=True)
