import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

from utils import clean_text, detect_language, detect_threats, detect_offensive_language
from database import db
from model_runtime import load_model_bundle, predict_with_confidence

app = FastAPI(title="Cyberbullying Detection System API", version="1.0.0")

# Enable CORS for React frontend (default Vite port is 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the trained models
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")
if not os.path.exists(MODEL_PATH):
    raise RuntimeError(f"Model file not found at {MODEL_PATH}. Please run train.py first.")

try:
    models = load_model_bundle(MODEL_PATH)
    cb_pipeline = models["cyberbullying_pipeline"]
    sent_pipeline = models["sentiment_pipeline"]
    model_type = models["model_type"]
    print(f"Machine learning models loaded successfully! Type: {model_type}")
except Exception as e:
    raise RuntimeError(f"Failed to load models: {e}")

# ===== JWT Configuration =====
SECRET_KEY = "your-secret-key-change-in-production"  # Change this in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            return None
        return {"user_id": user_id}
    except JWTError:
        return None

# ===== Request / Response Schemas =====
# Authentication Schemas
class RegisterRequest(BaseModel):
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., min_length=6, example="password123")
    full_name: str = Field(default="", example="John Doe")

class LoginRequest(BaseModel):
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., example="password123")

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_admin: bool
    created_at: str

# Existing Schemas
class AnalyzeRequest(BaseModel):
    text: str = Field(..., example="You are stupid and useless.")

class AnalyzeResponse(BaseModel):
    text: str
    cleaned_text: str
    category: str
    confidence: float
    sentiment: str
    language: str

class ChatMessageRequest(BaseModel):
    sender: str
    text: str

class ChatMessageResponse(BaseModel):
    sender: str
    text: str
    timestamp: str
    flagged: bool
    category: str

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Cyberbullying Detection System API is running",
        "models_loaded": cb_pipeline is not None and sent_pipeline is not None
    }

# ===== AUTHENTICATION ENDPOINTS =====
@app.post("/api/auth/register", response_model=dict)
def register(request: RegisterRequest):
    """Register a new user."""
    if db.user_exists(request.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    user = db.create_user(
        email=request.email,
        password=request.password,
        full_name=request.full_name
    )
    
    if user:
        return {
            "status": "success",
            "message": "User registered successfully",
            "user": user
        }
    else:
        raise HTTPException(status_code=400, detail="Registration failed")

@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """Login user and return access token."""
    user = db.verify_user_credentials(request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["id"]},
        expires_delta=access_token_expires
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user
    )

@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user(token: Optional[str] = None):
    """Get current user info from token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user = db.get_user_by_id(token_data["user_id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return UserResponse(**user)

@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_comment(request: AnalyzeRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    # 1. Preprocess the text
    cleaned = clean_text(text)
    
    # 2. Detect language
    lang = detect_language(text)
    
    category = None
    confidence = 0.5
    sentiment = "Neutral"
    
    # 3. Predict category
    if not cleaned:
        category = "Normal"
        confidence = 1.0
        sentiment = "Neutral"
    else:
        try:
            # Predict Cyberbullying Category using ML model first
            category, confidence = predict_with_confidence(cb_pipeline, cleaned)
            
            # Predict Sentiment
            sentiment = str(sent_pipeline.predict([cleaned])[0])
        except Exception as e:
            print(f"Prediction error: {e}")
            category = None
            
        # 4. Fallback / Safety Net Heuristics
        # Threat safety net: If it contains threat keywords, override to Threat if model predicted Normal or failed
        is_threat = detect_threats(text)
        is_offensive = detect_offensive_language(text)
        
        if is_threat and (category is None or category == "Normal"):
            category = "Threat"
            confidence = max(confidence, 0.95)
            sentiment = "Negative"
        # Offensive safety net: If it contains slurs and model predicted Normal or failed, override to Harassment
        elif is_offensive and (category is None or category == "Normal"):
            category = "Harassment"
            confidence = max(confidence, 0.90)
            sentiment = "Negative"
            
        if category is None:
            category = "Normal"
            confidence = 0.5
            sentiment = "Neutral"

    # 5. Log to the database for analytics
    db.add_log(
        text=text,
        category=category,
        confidence=confidence,
        sentiment=sentiment,
        language=lang
    )
    
    return AnalyzeResponse(
        text=text,
        cleaned_text=cleaned,
        category=category,
        confidence=confidence,
        sentiment=sentiment,
        language=lang
    )

@app.get("/api/analytics")
def get_analytics():
    try:
        return db.get_analytics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
def get_logs():
    try:
        # Return logs, newest first
        return db.get_logs()[::-1]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logs/clear")
def clear_logs():
    try:
        db.clear_logs()
        return {"status": "success", "message": "Logs cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/messages")
def get_chat_messages():
    try:
        return db.get_chat_messages()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/message", response_model=ChatMessageResponse)
def post_chat_message(request: ChatMessageRequest):
    sender = request.sender.strip() or "User"
    text = request.text.strip()
    
    if not text:
        raise HTTPException(status_code=400, detail="Message text cannot be empty")
    
    cleaned = clean_text(text)
    lang = detect_language(text)
    
    category = None
    confidence = 0.5
    sentiment = "Neutral"
    
    if not cleaned:
        category = "Normal"
        confidence = 1.0
        sentiment = "Neutral"
    else:
        try:
            category, confidence = predict_with_confidence(cb_pipeline, cleaned)
            sentiment = str(sent_pipeline.predict([cleaned])[0])
        except Exception as e:
            print(f"Chat prediction error: {e}")
            category = None
            
        # Fallback / Safety Net Heuristics
        is_threat = detect_threats(text)
        is_offensive = detect_offensive_language(text)
        
        if is_threat and (category is None or category == "Normal"):
            category = "Threat"
            confidence = max(confidence, 0.95)
            sentiment = "Negative"
        elif is_offensive and (category is None or category == "Normal"):
            category = "Harassment"
            confidence = max(confidence, 0.90)
            sentiment = "Negative"
            
        if category is None:
            category = "Normal"
            confidence = 0.5
            sentiment = "Neutral"
            
    flagged = category != "Normal"
    
    # 1. Save in chat message list
    msg = db.add_chat_message(
        sender=sender,
        text=text,
        flagged=flagged,
        category=category
    )
    
    # 2. Also record in analytics database
    db.add_log(
        text=text,
        category=category,
        confidence=confidence,
        sentiment=sentiment,
        language=lang
    )
    
    return ChatMessageResponse(
        sender=msg["sender"],
        text=msg["text"],
        timestamp=msg["timestamp"],
        flagged=msg["flagged"],
        category=msg["category"]
    )
