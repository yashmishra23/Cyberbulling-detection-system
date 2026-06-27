import os
from datetime import datetime, timedelta
import collections
import bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/safespace_db")

class MongoDatabase:
    def __init__(self):
        # tlsAllowInvalidCertificates works around the Python 3.14 / OpenSSL
        # TLS handshake incompatibility with MongoDB Atlas. Safe for development;
        # remove this flag (or set to False) when deploying with a proper CA bundle.
        try:
            self.client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
            self.db = self.client.get_database()
        except Exception:
            # Fallback if URI doesn't contain a default database name
            self.client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
            self.db = self.client["safespace_db"]

        self.logs_col = self.db["logs"]
        self.chat_col = self.db["chat_messages"]
        self.users_col = self.db["users"]

        # Defer the admin-seed check so the server can start even if Atlas
        # is momentarily unreachable. The seed runs on first actual request.
        self._admin_seeded = False

    def _ensure_admin(self):
        """Seed the admin user once, lazily, on the first database operation."""
        if self._admin_seeded:
            return
        try:
            if self.users_col.count_documents({}) == 0:
                self.create_user("admin@admin.com", "admin123", "Admin")
                self.users_col.update_one(
                    {"email": "admin@admin.com"},
                    {"$set": {"is_admin": True}}
                )
            self._admin_seeded = True
        except Exception:
            pass  # Will retry next call

    def add_log(self, text: str, category: str, confidence: float, sentiment: str, language: str):
        self._ensure_admin()
        log_entry = {
            "text": text,
            "category": category,
            "confidence": float(confidence),
            "sentiment": sentiment,
            "language": language,
            "timestamp": datetime.now().isoformat()
        }
        res = self.logs_col.insert_one(log_entry)
        log_entry["id"] = str(res.inserted_id)
        del log_entry["_id"]
        return log_entry

    def clear_logs(self):
        self.logs_col.delete_many({})

    def get_logs(self):
        logs = list(self.logs_col.find())
        for log in logs:
            log["id"] = str(log["_id"])
            del log["_id"]
        return logs

    def add_chat_message(self, sender: str, text: str, flagged: bool, category: str):
        msg = {
            "sender": sender,
            "text": text,
            "timestamp": datetime.now().isoformat(),
            "flagged": flagged,
            "category": category
        }
        self.chat_col.insert_one(msg)
        
        # Keep only last 50 chat messages
        if self.chat_col.count_documents({}) > 50:
            oldest = self.chat_col.find().sort("timestamp", 1).limit(1)
            for o in oldest:
                self.chat_col.delete_one({"_id": o["_id"]})
                
        if "_id" in msg:
            del msg["_id"]
        return msg

    def get_chat_messages(self):
        msgs = list(self.chat_col.find().sort("timestamp", 1))
        for msg in msgs:
            if "_id" in msg:
                del msg["_id"]
        return msgs

    def get_analytics(self):
        logs = self.get_logs()
        
        total = len(logs)
        if total == 0:
            return {
                "total_comments": 0,
                "toxic_comments": 0,
                "clean_comments": 0,
                "categories": {},
                "sentiment": {},
                "languages": {},
                "trends": [],
                "top_abusive_words": []
            }
            
        toxic_count = sum(1 for log in logs if log["category"] != "Normal")
        clean_count = total - toxic_count
        
        # Category counts
        categories_dict = collections.defaultdict(int)
        for log in logs:
            categories_dict[log["category"]] += 1
            
        # Sentiment counts
        sentiment_dict = collections.defaultdict(int)
        for log in logs:
            sentiment_dict[log["sentiment"]] += 1
            
        # Language counts
        language_dict = collections.defaultdict(int)
        for log in logs:
            language_dict[log["language"]] += 1

        # Trend over last 7 days
        trends = []
        now = datetime.now()
        dates_list = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        
        trends_data = {d: {"total": 0, "toxic": 0} for d in dates_list}
        for log in logs:
            try:
                log_date = log["timestamp"][:10]  # YYYY-MM-DD
                if log_date in trends_data:
                    trends_data[log_date]["total"] += 1
                    if log["category"] != "Normal":
                        trends_data[log_date]["toxic"] += 1
            except Exception:
                pass
                
        for d in dates_list:
            trends.append({
                "date": d,
                "total": trends_data[d]["total"],
                "toxic": trends_data[d]["toxic"]
            })

        # Top abusive words (frequency check on toxic comments)
        toxic_comments_text = " ".join([
            log["text"].lower() for log in logs if log["category"] != "Normal"
        ])
        
        # Quick clean
        import re
        words = re.sub(r'[^a-z\s]', '', toxic_comments_text).split()
        
        # Filter stopwords
        from utils import ENGLISH_STOPWORDS, HINGLISH_STOPWORDS
        ignored_words = ENGLISH_STOPWORDS.union(HINGLISH_STOPWORDS).union({"is", "am", "are", "you", "your", "my", "this", "that"})
        filtered_words = [w for w in words if len(w) > 2 and w not in ignored_words]
        
        top_words = collections.Counter(filtered_words).most_common(10)
        top_abusive_words = [{"word": w, "count": c} for w, c in top_words]

        return {
            "total_comments": total,
            "toxic_comments": toxic_count,
            "clean_comments": clean_count,
            "categories": dict(categories_dict),
            "sentiment": dict(sentiment_dict),
            "languages": dict(language_dict),
            "trends": trends,
            "top_abusive_words": top_abusive_words
        }

    # ===== USER MANAGEMENT METHODS =====
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    
    def user_exists(self, email: str) -> bool:
        """Check if a user exists by email."""
        return self.users_col.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}}) is not None
    
    def create_user(self, email: str, password: str, full_name: str = "") -> dict:
        """Create a new user. Returns user data or None if user already exists."""
        if self.user_exists(email):
            return None
        
        user = {
            "email": email.lower(),
            "password_hash": self.hash_password(password),
            "full_name": full_name,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "is_admin": False
        }
        
        res = self.users_col.insert_one(user)
        
        # Return user data without password hash
        return {
            "id": str(res.inserted_id),
            "email": user["email"],
            "full_name": user["full_name"],
            "created_at": user["created_at"]
        }
    
    def get_user_by_email(self, email: str) -> dict:
        """Get a user by email with password hash for authentication."""
        user = self.users_col.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}})
        if user:
            user["id"] = str(user["_id"])
            del user["_id"]
            return user
        return None
    
    def verify_user_credentials(self, email: str, password: str) -> dict:
        """Verify user credentials. Returns user data if valid, None otherwise."""
        user = self.get_user_by_email(email)
        if user and self.verify_password(password, user["password_hash"]):
            # Update last login
            from bson.objectid import ObjectId
            self.users_col.update_one(
                {"_id": ObjectId(user["id"])},
                {"$set": {"last_login": datetime.now().isoformat()}}
            )
            
            # Return user data without password hash
            return {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "is_admin": user.get("is_admin", False)
            }
        return None
    
    def get_user_by_id(self, user_id: str) -> dict:
        """Get a user by ID (returns data without password hash)."""
        from bson.objectid import ObjectId
        try:
            user = self.users_col.find_one({"_id": ObjectId(user_id)})
            if user:
                return {
                    "id": str(user["_id"]),
                    "email": user["email"],
                    "full_name": user["full_name"],
                    "is_admin": user.get("is_admin", False),
                    "created_at": user["created_at"]
                }
        except Exception:
            pass
        return None

db = MongoDatabase()
