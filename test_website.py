#!/usr/bin/env python3
"""
Test Channel Plus website functionality to understand current behavior
before migrating from Elixir to Python
"""

import requests
import re
import json
import sys
from urllib.parse import urljoin

def test_basic_structure():
    """Test the basic website structure using requests"""
    print("🔍 Testing Channel Plus Website Structure (Basic)")
    print("=" * 60)
    
    base_url = "https://channelplus.ner.gov.tw/viewalllang/390"
    test_url = f"{base_url}?page=1"
    
    try:
        print(f"📡 Testing URL: {test_url}")
        response = requests.get(test_url, timeout=15)
        print(f"✅ Status Code: {response.status_code}")
        print(f"📊 Content Length: {len(response.text)} chars")
        
        # Look for the JSON pattern that the Elixir code expects
        print("\n🔍 Searching for window.__PRELOADED_STATE__ pattern...")
        rule = r'window\.__PRELOADED_STATE__ = ({.+})'
        match = re.search(rule, response.text)
        
        if match:
            print("✅ Found window.__PRELOADED_STATE__ pattern!")
            json_str = match.group(1)
            
            try:
                parsed_data = json.loads(json_str)
                print("✅ JSON parsing successful")
                
                # Analyze structure following Elixir code logic
                print(f"🏗️  Top-level keys: {list(parsed_data.keys())}")
                
                if 'reducers' in parsed_data:
                    reducers = parsed_data['reducers']
                    print(f"📂 Reducers keys: {list(reducers.keys())}")
                    
                    if 'languageEpisode' in reducers:
                        lang_episode = reducers['languageEpisode']
                        print(f"🎵 languageEpisode keys: {list(lang_episode.keys())}")
                        
                        if 'data' in lang_episode:
                            episodes = lang_episode['data']
                            print(f"📚 Found {len(episodes)} episodes")
                            
                            if episodes:
                                sample_episode = episodes[0]
                                print(f"🎧 Sample episode keys: {list(sample_episode.keys())}")
                                
                                if 'audio' in sample_episode:
                                    audio_info = sample_episode['audio']
                                    print(f"🔊 Audio info keys: {list(audio_info.keys())}")
                                    
                                    if 'key' in audio_info and 'name' in audio_info:
                                        audio_key = audio_info['key']
                                        audio_name = audio_info['name']
                                        audio_url = f"https://channelplus.ner.gov.tw/api/audio/{audio_key}"
                                        
                                        print(f"🎵 Sample audio name: {audio_name}")
                                        print(f"🔗 Sample audio URL: {audio_url}")
                                        
                                        # Test audio URL accessibility
                                        try:
                                            audio_response = requests.head(audio_url, timeout=10)
                                            print(f"🎧 Audio URL status: {audio_response.status_code}")
                                            if audio_response.status_code == 200:
                                                content_type = audio_response.headers.get('Content-Type', 'unknown')
                                                content_length = audio_response.headers.get('Content-Length', 'unknown')
                                                print(f"🎼 Content-Type: {content_type}")
                                                print(f"📏 Content-Length: {content_length}")
                                        except Exception as e:
                                            print(f"❌ Audio URL test failed: {e}")
                                        
                                        return {
                                            'success': True,
                                            'episodes_found': len(episodes),
                                            'sample_audio_url': audio_url,
                                            'sample_audio_name': audio_name,
                                            'structure_valid': True,
                                            'all_episodes': episodes[:3]  # First 3 for analysis
                                        }
                                    else:
                                        print("❌ Audio key or name missing in episode")
                                else:
                                    print("❌ No audio info found in episode")
                            else:
                                print("❌ No episodes found in data array")
                        else:
                            print("❌ No 'data' key in languageEpisode")
                    else:
                        print("❌ No 'languageEpisode' in reducers")
                        print(f"Available reducer keys: {list(reducers.keys())}")
                else:
                    print("❌ No 'reducers' key found")
                    print(f"Available top-level keys: {list(parsed_data.keys())}")
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing failed: {e}")
                return {'success': False, 'error': f'JSON parsing failed: {e}'}
        else:
            print("❌ window.__PRELOADED_STATE__ pattern not found")
            # Search for alternative patterns
            print("\n🔍 Searching for alternative patterns...")
            patterns_to_check = [
                r'__PRELOADED_STATE__',
                r'window\.__INITIAL_STATE__',
                r'window\.initialState',
                r'data-reactroot'
            ]
            
            for pattern in patterns_to_check:
                if re.search(pattern, response.text):
                    print(f"📍 Found pattern: {pattern}")
            
            return {'success': False, 'error': 'Expected pattern not found'}
            
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return {'success': False, 'error': f'Request failed: {e}'}

def test_multiple_pages():
    """Test multiple pages to understand pagination"""
    print("\n🔍 Testing Multiple Pages")
    print("=" * 40)
    
    base_url = "https://channelplus.ner.gov.tw/viewalllang/390"
    results = {}
    
    for page_num in [1, 2, 3]:
        print(f"\n📄 Testing page {page_num}...")
        test_url = f"{base_url}?page={page_num}"
        
        try:
            response = requests.get(test_url, timeout=10)
            if response.status_code == 200:
                rule = r'window\.__PRELOADED_STATE__ = ({.+})'
                match = re.search(rule, response.text)
                
                if match:
                    data = json.loads(match.group(1))
                    episodes = data.get('reducers', {}).get('languageEpisode', {}).get('data', [])
                    results[page_num] = len(episodes)
                    print(f"✅ Page {page_num}: {len(episodes)} episodes")
                else:
                    results[page_num] = 0
                    print(f"❌ Page {page_num}: No data found")
            else:
                print(f"❌ Page {page_num}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ Page {page_num}: Error {e}")
    
    return results

if __name__ == "__main__":
    print("🎭 Channel Plus Website Analysis")
    print("=" * 60)
    
    # Test basic structure
    basic_result = test_basic_structure()
    
    # Test pagination if basic test succeeded
    if basic_result.get('success'):
        pagination_result = test_multiple_pages()
        print(f"\n📊 Pagination Results: {pagination_result}")
    
    print(f"\n📋 Final Analysis Result:")
    print(json.dumps(basic_result, indent=2, ensure_ascii=False))