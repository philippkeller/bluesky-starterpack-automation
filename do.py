#! /usr/bin/env python

"""
Usage:
    do.py add-starterpack
    do.py replies
"""

from atproto import Client
import emoji
import requests
from docopt import docopt
import datetime
import pycountry_convert
from collections import Counter

CURRENT_USER_DID = 'did:plc:cv7n7pa4fmtkgyzfl2rf4xn3'

def continent(country_code):
    if country_code in ['EU', 'EA']:
        return 'Europe'
    if country_code in ['UM']:
        return 'North America'
    if country_code in ['CP', 'IC']:
        return 'unknown'
    
    continent_code = pycountry_convert.country_alpha2_to_continent_code(country_code)
    return pycountry_convert.convert_continent_code_to_continent_name(continent_code)

def create_starterpack(name: str, user_ids: list[str], bearer_token: str) -> bool:
    """
    Create a starterpack list with the given name and user IDs.
    
    Args:
        name (str): Name of the starterpack (e.g. "#buildinpublic Switzerland")
        user_ids (list[str]): List of user DIDs to add to the starterpack
        bearer_token (str): The authentication token
        
    Returns:
        bool: True if successful, raises exception otherwise
    """
    base_url = "https://amanita.us-east.host.bsky.network/xrpc"
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'atproto-accept-labelers': 'did:plc:ar7c4by46qjdydhdevvrndac;redact',
        'authorization': f'Bearer {bearer_token}',
        'content-type': 'application/json',
        'origin': 'https://bsky.app',
        'priority': 'u=1, i',
        'referer': 'https://bsky.app/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    
    # Step 1: Create the list
    create_list_data = {
        "collection": "app.bsky.graph.list",
        "repo": CURRENT_USER_DID,
        "record": {
            "name": name,
            "createdAt": datetime.datetime.utcnow().isoformat() + "Z",
            "purpose": "app.bsky.graph.defs#referencelist",
            "$type": "app.bsky.graph.list"
        }
    }
    
    response = requests.post(f"{base_url}/com.atproto.repo.createRecord", 
                           headers=headers, 
                           json=create_list_data)
    response.raise_for_status()
    list_data = response.json()
    
    if list_data.get('validationStatus') != 'valid':
        raise Exception("List creation validation failed")
    
    list_uri = list_data['uri']
    
    # Step 2: Add users to the list
    writes = []
    current_time = datetime.datetime.utcnow().isoformat() + "Z"
    
    for user_id in user_ids:
        writes.append({
            "$type": "com.atproto.repo.applyWrites#create",
            "collection": "app.bsky.graph.listitem",
            "value": {
                "$type": "app.bsky.graph.listitem",
                "subject": user_id,
                "list": list_uri,
                "createdAt": current_time
            }
        })
    
    apply_writes_data = {
        "repo": CURRENT_USER_DID,
        "writes": writes
    }
    
    response = requests.post(f"{base_url}/com.atproto.repo.applyWrites", 
                           headers=headers, 
                           json=apply_writes_data)
    response.raise_for_status()
    writes_data = response.json()
    
    # Check all items were created successfully
    for result in writes_data.get('results', []):
        if result.get('validationStatus') != 'valid':
            raise Exception("User addition validation failed")
    
    # Step 3: Create the starterpack
    starterpack_data = {
        "collection": "app.bsky.graph.starterpack",
        "repo": CURRENT_USER_DID,
        "record": {
            "name": name,
            "list": list_uri,
            "feeds": [],
            "createdAt": datetime.datetime.utcnow().isoformat() + "Z",
            "$type": "app.bsky.graph.starterpack"
        }
    }
    
    response = requests.post(f"{base_url}/com.atproto.repo.createRecord", 
                           headers=headers, 
                           json=starterpack_data)
    response.raise_for_status()
    
    return True

def emoji_to_code(flag_emoji):
    # Convert the flag emoji to the regional indicator letters
    codes = [c for c in flag_emoji]
    # Convert the regional indicator symbols to regular letters
    country_code = ''.join(chr(ord(c) - 127397) for c in codes)
    return country_code

def country_code_from_emoji(char):
    # Method 1: Check for regional indicator symbols (most country flags)
    if len(char) == 2 and all(0x1F1E6 <= ord(c) <= 0x1F1FF for c in char):
        return emoji_to_code(char)
    
    # Method 2: Check for other special flag emojis
    if emoji.demojize(char).startswith(':flag_'):
        country_code = emoji.demojize(char)[6:]
        return emoji_to_code(country_code)
    
    else:
        return None

if __name__ == "__main__":
    import os
    import dotenv
    dotenv.load_dotenv()

    args = docopt(__doc__)

    bearer_token = open('.bearer').read().split(' ')[1]

    if args['add-starterpack']:
        user_ids = [
            "did:plc:cv7n7pa4fmtkgyzfl2rf4xn3",
            "did:plc:phuqmj3y6qv3egonxkbf5byw",
            "did:plc:vf7tv7uq23avbpzkjswlv273",
            "did:plc:udvbq6dntlp3huisidgytqju",
            "did:plc:zivbusxwcsom5o6mf7kljzms",
            "did:plc:2b2lqipf3vklnfslluzsqiso",
            "did:plc:zxzqwrj6v6c2phtfzukqxctv",
            "did:plc:wpfo56wcy4vem72u3vwl33q7"
        ]
        create_starterpack('locco', user_ids, bearer_token)
    elif args['replies']:
        countries = Counter()
        continents = Counter()
        client = Client()
        # read password from .env file: BSKY_PASSWORD
        client.login('philippkeller.com', os.getenv('BSKY_PASSWORD'))

        # go to post, view source and look for at://…
        post_uri = f'at://{CURRENT_USER_DID}/app.bsky.feed.post/3lbodzewg4k2l'
        post = client.get_post_thread(post_uri)
        # print(f'got {len(post["thread"]["replies"])} replies')
        for reply in post['thread']['replies']:
            text = reply['post']['record']['text']
            # get emojis
            for e in emoji.emoji_list(text):
                flag = country_code_from_emoji(e['emoji'])
                if flag:
                    continent_name = continent(flag)
                    countries[flag] += 1
                    continents[continent_name] += 1
                    break
        
        for country_code, count in countries.most_common(10):
            print(f'{country_code} {count}')

        for continent_name, count in continents.most_common():
            print(f'{continent_name} {count}')
