from pymongo import MongoClient

# Setup MongoDB client and select DB and collection
client = MongoClient('mongodb://localhost:27017/')  # Adjust URI if needed
db = client['NoWaste']
foodPosted = db['FoodPost']
foodConfirmed=db['FoodCollected']
ngo_col=db['ngos']
users_col = db['users']