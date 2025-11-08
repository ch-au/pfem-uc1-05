#!/usr/bin/env python3
"""
Quick test script for backend API endpoints
Run this after starting the FastAPI server to test chat and quiz functionality
"""
import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def print_response(title: str, response: requests.Response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(response.text)
    print()

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print_response("Health Check", response)
    return response.status_code == 200

def test_chat():
    """Test chatbot functionality"""
    print("\n" + "="*60)
    print("TESTING CHATBOT MODE")
    print("="*60)
    
    # Create session
    print("\n1. Creating chat session...")
    response = requests.post(
        f"{BASE_URL}/chat/session",
        json={"metadata": {"test": True}}
    )
    print_response("Create Session", response)
    
    if response.status_code != 200:
        return False
    
    session_id = response.json()["session_id"]
    print(f"✓ Session ID: {session_id}")
    
    # Send message - data query
    print("\n2. Sending data query...")
    response = requests.post(
        f"{BASE_URL}/chat/message",
        json={
            "session_id": session_id,
            "message": "Wer ist der Top-Torschütze von Mainz 05?"
        }
    )
    print_response("Data Query Response", response)
    
    if response.status_code != 200:
        return False
    
    # Send message - general question
    print("\n3. Sending general question...")
    response = requests.post(
        f"{BASE_URL}/chat/message",
        json={
            "session_id": session_id,
            "message": "Erzähle mir etwas über die Geschichte von Mainz 05."
        }
    )
    print_response("General Question Response", response)
    
    # Get history
    print("\n4. Retrieving chat history...")
    response = requests.get(f"{BASE_URL}/chat/history/{session_id}")
    print_response("Chat History", response)
    
    return True

def test_quiz():
    """Test quiz functionality"""
    print("\n" + "="*60)
    print("TESTING QUIZ MODE")
    print("="*60)
    
    # Create game
    print("\n1. Creating quiz game...")
    response = requests.post(
        f"{BASE_URL}/quiz/game",
        json={
            "topic": "Spieler",
            "difficulty": "medium",
            "num_rounds": 3,
            "player_names": ["Alice", "Bob"]
        }
    )
    print_response("Create Game", response)
    
    if response.status_code != 200:
        return False
    
    game_id = response.json()["game_id"]
    print(f"✓ Game ID: {game_id}")
    
    # Start game
    print("\n2. Starting game...")
    response = requests.post(f"{BASE_URL}/quiz/game/{game_id}/start")
    print_response("Start Game", response)
    
    if response.status_code != 200:
        return False
    
    # Get current question
    print("\n3. Getting current question...")
    response = requests.get(f"{BASE_URL}/quiz/game/{game_id}/question")
    print_response("Get Question", response)
    
    if response.status_code != 200:
        return False
    
    question_data = response.json()
    round_id = question_data["round_id"]
    options = question_data["options"]
    correct_answer = None
    
    # Find correct answer (it's in the options, but we need to check)
    print(f"\nQuestion: {question_data['question_text']}")
    print(f"Options: {options}")
    
    # Submit answer (using first option)
    print("\n4. Submitting answer...")
    selected_answer = options[0]
    response = requests.post(
        f"{BASE_URL}/quiz/game/{game_id}/answer",
        json={
            "round_id": round_id,
            "answer": {
                "player_name": "Alice",
                "answer": selected_answer,
                "time_taken": 5.5
            }
        }
    )
    print_response("Submit Answer", response)
    
    # Submit answer for second player
    print("\n5. Submitting answer for second player...")
    selected_answer = options[1]
    response = requests.post(
        f"{BASE_URL}/quiz/game/{game_id}/answer",
        json={
            "round_id": round_id,
            "answer": {
                "player_name": "Bob",
                "answer": selected_answer,
                "time_taken": 8.2
            }
        }
    )
    print_response("Submit Answer (Player 2)", response)
    
    # Get leaderboard
    print("\n6. Getting leaderboard...")
    response = requests.get(f"{BASE_URL}/quiz/game/{game_id}/leaderboard")
    print_response("Leaderboard", response)
    
    # Advance to next round
    print("\n7. Advancing to next round...")
    response = requests.post(f"{BASE_URL}/quiz/game/{game_id}/next")
    print_response("Advance Round", response)
    
    # Get game state
    print("\n8. Getting game state...")
    response = requests.get(f"{BASE_URL}/quiz/game/{game_id}")
    print_response("Game State", response)
    
    return True

def main():
    """Run all tests"""
    print("="*60)
    print("BACKEND API TEST SUITE")
    print("="*60)
    print("\nMake sure the FastAPI server is running on http://localhost:8000")
    print("Press Enter to continue...")
    input()
    
    # Test health
    if not test_health():
        print("❌ Health check failed! Is the server running?")
        return
    
    # Test chat
    try:
        test_chat()
        print("✅ Chat tests completed")
    except Exception as e:
        print(f"❌ Chat test failed: {e}")
    
    # Test quiz
    try:
        test_quiz()
        print("✅ Quiz tests completed")
    except Exception as e:
        print(f"❌ Quiz test failed: {e}")
    
    print("\n" + "="*60)
    print("TESTING COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()


