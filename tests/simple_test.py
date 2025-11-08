#!/usr/bin/env python3
"""
Simple test script for the API
Run this after starting the server with: python start_server.py
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test if server is running"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Server is running!")
            print(f"   Status: {response.json()}")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Is it running?")
        print("   Start it with: python start_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_chat():
    """Test chatbot functionality"""
    print("\n💬 Testing Chatbot Mode...")
    
    # Create session
    print("  1. Creating chat session...")
    response = requests.post(f"{BASE_URL}/chat/session", json={})
    if response.status_code != 200:
        print(f"  ❌ Failed: {response.status_code}")
        return False
    
    session_id = response.json()["session_id"]
    print(f"     ✅ Session created: {session_id[:8]}...")
    
    # Send data query
    print("  2. Sending data query...")
    response = requests.post(
        f"{BASE_URL}/chat/message",
        json={
            "session_id": session_id,
            "message": "Wer ist der Top-Torschütze von Mainz 05?"
        }
    )
    if response.status_code == 200:
        data = response.json()
        print(f"     ✅ Answer: {data['answer'][:100]}...")
        print(f"     📊 Is data query: {data['is_data_query']}")
    else:
        print(f"     ❌ Failed: {response.status_code}")
        return False
    
    return True

def test_quiz():
    """Test quiz functionality"""
    print("\n🎯 Testing Quiz Mode...")
    
    # Create game
    print("  1. Creating quiz game...")
    response = requests.post(
        f"{BASE_URL}/quiz/game",
        json={
            "topic": "Spieler",
            "difficulty": "medium",
            "num_rounds": 2,
            "player_names": ["Alice", "Bob"]
        }
    )
    if response.status_code != 200:
        print(f"  ❌ Failed: {response.status_code}")
        return False
    
    game_id = response.json()["game_id"]
    print(f"     ✅ Game created: {game_id[:8]}...")
    
    # Start game
    print("  2. Starting game...")
    response = requests.post(f"{BASE_URL}/quiz/game/{game_id}/start")
    if response.status_code != 200:
        print(f"     ❌ Failed: {response.status_code}")
        return False
    print("     ✅ Game started")
    
    # Get question
    print("  3. Getting question...")
    response = requests.get(f"{BASE_URL}/quiz/game/{game_id}/question")
    if response.status_code != 200:
        print(f"     ❌ Failed: {response.status_code}")
        return False
    
    question = response.json()
    print(f"     ✅ Question: {question['question_text'][:60]}...")
    print(f"     📝 Options: {len(question['options'])} choices")
    
    # Submit answer
    print("  4. Submitting answer...")
    round_id = question["round_id"]
    selected_answer = question["options"][0]
    
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
    if response.status_code == 200:
        result = response.json()
        print(f"     ✅ Answer submitted")
        print(f"     {'🎉 Correct!' if result['correct'] else '❌ Wrong'}")
        print(f"     🏆 Points earned: {result['points_earned']}")
    else:
        print(f"     ❌ Failed: {response.status_code}")
        return False
    
    # Get leaderboard
    print("  5. Getting leaderboard...")
    response = requests.get(f"{BASE_URL}/quiz/game/{game_id}/leaderboard")
    if response.status_code == 200:
        leaderboard = response.json()["leaderboard"]
        print(f"     ✅ Leaderboard:")
        for i, entry in enumerate(leaderboard, 1):
            print(f"        {i}. {entry['player_name']}: {entry['total_points']} points")
    else:
        print(f"     ❌ Failed: {response.status_code}")
    
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("MAINZ 05 QUIZ & CHATBOT API - TEST SUITE")
    print("=" * 60)
    
    # Check if server is running
    if not test_health():
        print("\n❌ Health check failed. Please start the server first:")
        print("   python start_server.py")
        return
    
    # Test chat
    try:
        if test_chat():
            print("\n✅ Chatbot tests passed!")
        else:
            print("\n❌ Chatbot tests failed")
    except Exception as e:
        print(f"\n❌ Chatbot test error: {e}")
    
    # Test quiz
    try:
        if test_quiz():
            print("\n✅ Quiz tests passed!")
        else:
            print("\n❌ Quiz tests failed")
    except Exception as e:
        print(f"\n❌ Quiz test error: {e}")
    
    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()


