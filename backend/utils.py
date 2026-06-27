import re

# Standard English stopwords (excluding key negative terms like 'not', 'no', 'never' which carry sentiment)
ENGLISH_STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
    "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
    "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", 
    "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", 
    "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", 
    "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", 
    "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", 
    "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
    "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", 
    "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", 
    "most", "other", "some", "such", "only", "own", "same", "so", "than", "too", "very", 
    "s", "t", "can", "will", "just", "don", "should", "now"
}

# Common Hinglish stopwords (excluding key negative terms)
HINGLISH_STOPWORDS = {
    "aur", "ko", "se", "ka", "ki", "ke", "me", "mein", "par", "bhi", "hi", "toh", "tum", 
    "aap", "tera", "teri", "tere", "mera", "meri", "mere", "hum", "humein", "tumhe", 
    "apna", "apni", "apne", "wo", "woh", "hai", "hain", "tha", "thi", "the", "ho", "hona", 
    "karna", "kar", "raha", "rahi", "rahe", "diya", "liya", "gaya", "gayi", "gaye", 
    "kuch", "sab", "yeh", "yahi", "wahi", "is", "us", "ab", "kab", "tab", "jab", "na", 
    "yaar", "chal", "rha", "rhi", "rhe", "hai", "h", "he", "tha", "thaa"
}

# A vocabulary of common Hindi/Hinglish words to identify Hinglish comments
HINGLISH_INDICATORS = {
    "tum", "aap", "tujhe", "tera", "teri", "tere", "mera", "meri", "mere", "tumhe", "apna", "apni", 
    "apne", "woh", "hai", "hain", "gaya", "gayi", "gaye", "bahut", "bhut", "bhai", "yaar", 
    "kya", "kyu", "kyoon", "kyun", "kab", "kahaan", "kahan", "kaise", "kon", "kaun", 
    "ganda", "pagal", "bewakoof", "bewakuf", "saala", "sala", "kutte", "kutta", "kamina", 
    "kamini", "chutiya", "harami", "gadhe", "gadha", "log", "logo", "logon", "karne", 
    "rha", "rhi", "rhe", "bhi", "toh", "to", "mat", "nahi", "nahin", "naa", "nai", "nh", 
    "chal", "nikal", "mar", "marna", "fek", "fake", "bakwaas", "bakwas", "faltu", "faaltu",
    "dunga", "aaya", "maar", "jaan", "agar", "samne", "sath", "saath", "liye", "pe", "per", "nhi"
}

def clean_text(text: str) -> str:
    """
    Cleans raw text: lowercases, removes URLs/mentions/hashtags, preserves emojis, key punctuation, and words.
    Does NOT remove numbers, punctuation, or pronouns/stopwords that carry sequence/directional semantics.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Lowercase
    text = text.lower()
    
    # 2. Remove HateXplain placeholder tokens
    text = re.sub(r'<(number|user|percent|money|time|date|url|censored)>', ' ', text)
    
    # 3. Remove URLs, mentions (@), hashtags (#)
    text = re.sub(r'http\S+|www\S+|https\S+', '', text)
    text = re.sub(r'@\w+|#\w+', '', text)
    
    # 4. Keep letters, numbers, spaces, key punctuation, and emojis/symbols
    # Keep alphanumeric, spaces, hyphen, exclamation, question, dot, at, hash, and emojis (U+10000 and above)
    text = re.sub(r'[^\w\s\-!?.@#\U00010000-\U0010ffff]', ' ', text)
    
    # 5. Collapse multiple spaces
    return " ".join(text.split())

def detect_language(text: str) -> str:
    """
    Heuristic-based language detection to identify English vs Hinglish.
    """
    if not text:
        return "English"
    
    # Tokenize words
    words = re.sub(r'[^a-zA-Z\s]', ' ', text.lower()).split()
    if not words:
        return "English"
    
    # Combine indicators and stopwords for language checks
    hinglish_vocab = HINGLISH_INDICATORS.union(HINGLISH_STOPWORDS)
    hinglish_count = sum(1 for w in words if w in hinglish_vocab)
    
    # If any word is a distinct Hinglish word or ratio of Hinglish is high, mark as Hinglish
    ratio = hinglish_count / len(words)
    if ratio >= 0.15 or hinglish_count >= 2:
        return "Hinglish"
    
    return "English"


# Threat keywords in English and Hinglish
THREAT_KEYWORDS = {
    # English threats
    "kill", "murder", "shoot", "stab", "hurt", "attack", "beat", "punch", "die", "dead",
    "death", "destroy", "harm", "violence", "violent", "threat", "threaten", "punch", 
    "hit", "kick", "bomb", "rape", "assault", "kidnap", "torture", "poison",
    # Hinglish/Hindi threats
    "maar", "mara", "marvaunga", "mar", "jaan", "jani", "maut", "maar dunga", "tujhe",
    "tumhe", "goli", "talwar", "kutare", "kuthar", "khala", "pakda", "phaadi", "paltan",
    "bhaag", "bhaag jao", "nikal", "phek", "maar ke", "gore", "dhopal", "jhhapad",
    "takatak", "takol", "takoli", "takari", "takra", "takregi", "takrar",
}

# Offensive/slur keywords for Harassment, Hate Speech, etc
OFFENSIVE_KEYWORDS = {
    # Ethnic/racist slurs
    "dirty", "filthy", "trash", "garbage", "scum", "vermin", "subhuman",
    "pig", "pig!", "piggy", "dog", "donkey", "ass", "idiot", "moron", "imbecile",
    "stupid", "dumb", "retard", "retarded", "fool", "loser", "pathetic",
    # Gender-based insults
    "bitch", "bastard", "whore", "slut", "hag", "cunt",
    # Religious insults
    "infidel", "blasphemy", "godless", "heathen", "cult",
    # Hindi/Hinglish slurs
    "kutte", "kutta", "suar", "saala", "sala", "bhenchod", "madharchod",
    "harami", "bewakoof", "kamina", "gadha", "gadhe", "chakka", "hijra",
    "nikamma", "bekar", "bekaara",
}

def detect_threats(text: str) -> bool:
    """
    Detect if text contains threat keywords in English or Hinglish.
    """
    if not text:
        return False
    
    text_lower = text.lower()
    words = re.sub(r'[^a-zA-Z\s]', ' ', text_lower).split()
    
    # Check for threat keywords
    return any(word in THREAT_KEYWORDS for word in words)


def detect_offensive_language(text: str) -> bool:
    """
    Detect if text contains offensive/slur keywords for harassment/hate speech classification.
    """
    if not text:
        return False
    
    text_lower = text.lower()
    words = re.sub(r'[^a-zA-Z\s]', ' ', text_lower).split()
    
    # Check for offensive keywords
    return any(word in OFFENSIVE_KEYWORDS for word in words)
