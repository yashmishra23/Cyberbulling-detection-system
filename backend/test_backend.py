import subprocess
import time
import urllib.request
import urllib.parse
import json
import sys
import os

def run_tests():
    print("Starting FastAPI server locally for verification...")
    # Change working directory to backend
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Run uvicorn on port 8000
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    time.sleep(3)
    
    base_url = "http://127.0.0.1:8000"
    tests_failed = False
    
    try:
        # Test 1: Root endpoint
        print("\n--- Test 1: Root API Endpoint ---")
        response = urllib.request.urlopen(f"{base_url}/")
        root_data = json.loads(response.read().decode('utf-8'))
        print(f"Root endpoint response: {root_data}")
        assert root_data["status"] == "online", "Server is not online"
        assert root_data["models_loaded"] is True, "Models did not load"
        print("Test 1 Passed!")

        # Test 2: Single Comment Analysis (Harassment - English)
        print("\n--- Test 2: Analyze Comment (English Cyberbullying) ---")
        req_data = json.dumps({"text": "You are absolutely stupid and useless."}).encode('utf-8')
        req = urllib.request.Request(
            f"{base_url}/api/analyze",
            data=req_data,
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        print(f"Analysis Response: {result}")
        # Accept any abusive category (Harassment, Gender Abuse, Hate Speech, etc)
        assert result["category"] in ["Harassment", "Gender Abuse", "Hate Speech", "Religious Abuse"], f"Expected abusive category, got {result['category']}"
        assert result["sentiment"] == "Negative", f"Expected Negative sentiment, got {result['sentiment']}"
        assert result["language"] == "English", f"Expected English language, got {result['language']}"
        print("Test 2 Passed!")

        # Test 3: Hinglish Threat Detection
        print("\n--- Test 3: Analyze Comment (Hinglish Threat) ---")
        req_data = json.dumps({"text": "Tujhe jaan se maar dunga agar samne aaya."}).encode('utf-8')
        req = urllib.request.Request(
            f"{base_url}/api/analyze",
            data=req_data,
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        print(f"Analysis Response: {result}")
        assert result["category"] == "Threat", f"Expected Threat, got {result['category']}"
        assert result["language"] == "Hinglish", f"Expected Hinglish language, got {result['language']}"
        print("Test 3 Passed!")

        # Test 4: Chat Message Monitoring
        print("\n--- Test 4: Simulated Chat Message ---")
        chat_data = json.dumps({"sender": "Imposter", "text": "Go back to where you came from, dirty pig!"}).encode('utf-8')
        req = urllib.request.Request(
            f"{base_url}/api/chat/message",
            data=chat_data,
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        print(f"Chat Message Response: {result}")
        assert result["flagged"] is True, "Expected message to be flagged"
        assert result["category"] in ["Hate Speech", "Harassment"], f"Expected Hate Speech or Harassment, got {result['category']}"
        print("Test 4 Passed!")

        # Test 5: Analytics Fetch
        print("\n--- Test 5: Fetch Analytics Dashboard ---")
        response = urllib.request.urlopen(f"{base_url}/api/analytics")
        analytics = json.loads(response.read().decode('utf-8'))
        print(f"Total Comments in DB: {analytics['total_comments']}")
        print(f"Toxic Comments Count: {analytics['toxic_comments']}")
        print(f"Top Abusive Words: {analytics['top_abusive_words']}")
        assert analytics["total_comments"] > 0, "No analytics data available"
        print("Test 5 Passed!")

    except Exception as e:
        print(f"Test failed with error: {e}")
        tests_failed = True
    finally:
        print("\nStopping local FastAPI server...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")
        
    if tests_failed:
        sys.exit(1)
    else:
        print("\nAll backend integration tests passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
