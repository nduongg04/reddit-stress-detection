#!/usr/bin/env python3
"""
⚠️ DEPRECATED - DO NOT USE ⚠️

Direct test Ollama API to debug labeling issue (DEPRECATED)

This script was used to debug Ollama local LLM performance.
Ollama has been removed from the pipeline and replaced with Groq Cloud API.

USE INSTEAD: Test Groq with scripts/label_with_groq.py

Date deprecated: 2025-12-20
"""

import sys
print("="*70)
print("⚠️  ERROR: Ollama has been removed from pipeline")
print("="*70)
print("\nOllama service removed from docker-compose.yml")
print("Replaced with Groq Cloud API (FREE, faster)")
print("\n✅ USE INSTEAD:")
print("  python scripts/label_with_groq.py")
print("="*70)
sys.exit(1)

# Original code preserved below for reference
# ============================================
"""
"""
import requests
import json

def test_ollama():
    url = "http://localhost:11434/api/generate"
    
    # Test with a clearly stressful Vietnamese text
    test_text = """25 tuổi đang khủng hoảng muốn bắt đầu học IT lại từ đầu có ổn không anh em? 
    Mình vừa mới bị lay off ngành sales. Thực ra em cũng cảm nhận được con người mình hướng nội 
    không phù hợp nghề sales cho lắm. Đang cảm thấy bế tắc và lo lắng về tương lai."""
    
    # Simple test first
    prompt = "Hello, how are you?"
    
    payload = {
        "model": "llama3.1:8b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9
        }
    }
    
    print("Sending request to Ollama...")
    print(f"Prompt length: {len(prompt)} characters\n")
    
    response = requests.post(url, json=payload, timeout=60)
    result = response.json()
    
    output = result.get('response', '').strip()
    
    print("="*70)
    print("OLLAMA RAW OUTPUT:")
    print("="*70)
    print(output)
    print("\n" + "="*70)
    
    # Try to parse JSON
    try:
        parsed = json.loads(output)
        print("\n✓ Successfully parsed as JSON:")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except json.JSONDecodeError as e:
        print(f"\n✗ Failed to parse as JSON: {e}")
        print("\nThis is why all confidence scores are 0.0!")

if __name__ == '__main__':
    test_ollama()
