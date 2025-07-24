#!/usr/bin/env python3
"""
Test different authentication approaches for Channel Plus audio downloads
"""

import requests
import time
import json
import re

def test_audio_download_methods():
    """Test various methods to download audio files"""
    
    # Get a sample audio URL from the main page
    main_url = "https://channelplus.ner.gov.tw/viewalllang/390?page=1"
    session = requests.Session()
    
    print("🔍 Testing Audio Download Authentication Methods")
    print("=" * 60)
    
    # Step 1: Get the main page and extract audio URL
    print("📄 Step 1: Getting main page data...")
    response = session.get(main_url)
    
    if response.status_code == 200:
        rule = r'window\.__PRELOADED_STATE__ = ({.+})'
        match = re.search(rule, response.text)
        
        if match:
            data = json.loads(match.group(1))
            episodes = data['reducers']['languageEpisode']['data']
            sample_episode = episodes[0]
            audio_key = sample_episode['audio']['key']
            audio_name = sample_episode['audio']['name']
            audio_url = f"https://channelplus.ner.gov.tw/api/audio/{audio_key}"
            
            print(f"✅ Found sample audio: {audio_name}")
            print(f"🔗 Audio URL: {audio_url}")
            
            # Test Method 1: Direct request (we know this returns 401)
            print("\n🧪 Method 1: Direct request...")
            response1 = session.get(audio_url)
            print(f"Status: {response1.status_code}")
            
            # Test Method 2: With proper headers
            print("\n🧪 Method 2: With browser headers...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': main_url,
                'Accept': 'audio/mpeg,audio/*,*/*',
                'Accept-Language': 'en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7',
                'Accept-Encoding': 'identity',
                'Connection': 'keep-alive',
            }
            response2 = session.get(audio_url, headers=headers)
            print(f"Status: {response2.status_code}")
            if response2.status_code == 200:
                print(f"✅ Success! Content-Type: {response2.headers.get('Content-Type')}")
                print(f"📏 Content-Length: {response2.headers.get('Content-Length')}")
            
            # Test Method 3: Check if we need to visit the episode page first
            print("\n🧪 Method 3: Visit episode page first...")
            episode_url = f"https://channelplus.ner.gov.tw/viewalllang/390/episode/{sample_episode['_id']}"
            session.get(episode_url)  # Visit episode page
            response3 = session.get(audio_url, headers=headers)
            print(f"Status: {response3.status_code}")
            if response3.status_code == 200:
                print(f"✅ Success! Content-Type: {response3.headers.get('Content-Type')}")
            
            # Test Method 4: Check cookies after visiting main page
            print("\n🧪 Method 4: Analyzing session cookies...")
            print(f"Cookies after main page: {len(session.cookies)} cookies")
            for cookie in session.cookies:
                print(f"  - {cookie.name}: {cookie.value[:20]}...")
            
            # Test with all accumulated cookies
            response4 = session.get(audio_url, headers=headers)
            print(f"Status with cookies: {response4.status_code}")
            
            # Test Method 5: Try different audio URLs to see if it's key-specific
            print("\n🧪 Method 5: Testing multiple audio URLs...")
            for i, episode in enumerate(episodes[:3]):
                test_audio_url = f"https://channelplus.ner.gov.tw/api/audio/{episode['audio']['key']}"
                test_response = session.get(test_audio_url, headers=headers)
                print(f"Episode {i+1} ({episode['audio']['name'][:30]}...): {test_response.status_code}")
            
            return {
                'main_page_status': 200,
                'sample_audio_url': audio_url,
                'test_results': {
                    'direct': response1.status_code,
                    'with_headers': response2.status_code,
                    'after_episode_visit': response3.status_code,
                    'with_cookies': response4.status_code
                }
            }
        else:
            print("❌ Could not find JSON data in main page")
            return {'error': 'No JSON data found'}
    else:
        print(f"❌ Failed to get main page: {response.status_code}")
        return {'error': f'Main page error: {response.status_code}'}

def analyze_network_requirements():
    """Analyze what network requirements might be needed"""
    print("\n🌐 Network Requirements Analysis")
    print("=" * 40)
    
    # Check if there are any specific network patterns we need to follow
    session = requests.Session()
    
    # Get main page and analyze all network requests patterns
    main_url = "https://channelplus.ner.gov.tw/viewalllang/390"
    
    print(f"🔍 Analyzing main page: {main_url}")
    response = session.get(main_url)
    
    # Look for any API calls or patterns in the page content
    content = response.text
    
    # Check for API endpoints
    api_patterns = re.findall(r'https://channelplus\.ner\.gov\.tw/api/[^"\']*', content)
    if api_patterns:
        print(f"📡 Found API endpoints in page:")
        for pattern in set(api_patterns[:5]):  # Show first 5 unique patterns
            print(f"  - {pattern}")
    
    # Check for any authentication-related JavaScript
    auth_patterns = re.findall(r'auth|token|session|csrf', content, re.IGNORECASE)
    if auth_patterns:
        print(f"🔐 Found auth-related terms: {len(set(auth_patterns))} unique")
    
    # Check response headers for security
    print(f"\n🛡️ Security headers:")
    security_headers = ['set-cookie', 'x-csrf-token', 'authorization', 'x-api-key']
    for header in security_headers:
        if header in response.headers:
            print(f"  - {header}: {response.headers[header][:50]}...")

if __name__ == "__main__":
    result = test_audio_download_methods()
    analyze_network_requirements()
    
    print(f"\n📋 Summary:")
    print(json.dumps(result, indent=2, ensure_ascii=False))