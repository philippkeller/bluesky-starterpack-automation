#! /usr/bin/env python

"""
Usage:
    do.py add-starterpack
    do.py replies
    do.py starter <uri>
    do.py starter-packs
"""

from atproto import Client
import emoji
import requests
from docopt import docopt
import datetime
import pycountry_convert
from collections import Counter
from joblib import Memory
from collections import defaultdict
import json
import os
import pycountry
CURRENT_USER_DID = 'did:plc:cv7n7pa4fmtkgyzfl2rf4xn3'

# Create a cache directory in the current folder
memory = Memory(".cache", verbose=0)

def get_all_starter_packs():
    from atproto import models
    client = Client()
    client.login('philippkeller.com', os.getenv('BSKY_PASSWORD'))
    params = models.AppBskyGraphGetActorStarterPacks.Params(actor=CURRENT_USER_DID)
    res = client.app.bsky.graph.get_actor_starter_packs(params)
    for i in res['starter_packs']:
        name = i['record']['name']
        uri = i['uri']
        print(name, uri)
    return res

def get_starter_pack_members(uri):
    from atproto import models
    client = Client()
    client.login('philippkeller.com', os.getenv('BSKY_PASSWORD'))
    params = models.AppBskyGraphGetStarterPack.Params(starter_pack=uri)
    res = client.app.bsky.graph.get_starter_pack(params)
    list_uri = res['starter_pack']['record']['list']
    params = models.AppBskyGraphGetList.Params(list=list_uri)
    list = client.app.bsky.graph.get_list(params)
    return [l['subject']['did'] for l in list['items']]

# Wrap the get_post_thread function
@memory.cache
def get_cached_post_thread(post_uri):
    client = Client()
    client.login('philippkeller.com', os.getenv('BSKY_PASSWORD'))
    return client.get_post_thread(post_uri)

def continent(country_code):
    if country_code in ['EU', 'EA']:
        return 'Europe'
    if country_code in ['UM']:
        return 'North America'
    if country_code in ['CP', 'IC']:
        return None
    
    continent_code = pycountry_convert.country_alpha2_to_continent_code(country_code)
    return pycountry_convert.convert_continent_code_to_continent_name(continent_code)

def create_starterpack(name: str, user_ids: list[str]) -> str:
    """
    Create a starterpack list with the given name and user IDs.
    If a list with the same name exists, returns its URI instead of creating a new one.
    
    Returns:
        str: The list URI (either existing or newly created)
    """
    # Check if list already exists
    storage_file = 'starterpacks.json'
    existing_lists = {}
    
    if os.path.exists(storage_file):
        with open(storage_file, 'r') as f:
            existing_lists = json.load(f)
        
        if name in existing_lists:
            return existing_lists[name]
    
    import time
    
    # check if bearer token file is younger than 1 hour
    if os.path.exists('.bearer') and os.path.getmtime('.bearer') > time.time() - 3600:
        bearer_token = open('.bearer').read().split(' ')[1]
    else:
        raise Exception("Bearer token is too old")
    
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
    starter_pack_uri = response.json()['uri']
    
    # After successful creation, store the new list_uri
    existing_lists[name] = starter_pack_uri
    with open(storage_file, 'w') as f:
        json.dump(existing_lists, f, indent=2)
    
    return starter_pack_uri

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
        create_starterpack('locco', user_ids)
    elif args['replies']:
        countries = Counter()
        continents = Counter()

        country_dids = defaultdict(list)
        
        post_uri = f'at://{CURRENT_USER_DID}/app.bsky.feed.post/3lbodzewg4k2l'
        # Now call without client
        post = get_cached_post_thread(post_uri)

        for i, reply in enumerate(post['thread']['replies']):
            text_original = reply['post']['record']['text']
            did = reply['post']['author']['did']
            # if text has " in " in it (e.g. "living in …") then take 2nd part
            if " in " in text_original:
                text = text_original.split(" in ", 1)[1]
            else:
                text = text_original
            # get emojis
            country_code = None
            for e in emoji.emoji_list(text):
                country_code = country_code_from_emoji(e['emoji'])
                if country_code:
                    continent_name = continent(country_code)
                    countries[country_code] += 1
                    continents[continent_name] += 1
                    country_dids[country_code].append(did)
                    break
            # if flag:
            #     print(f'{text_original} -> {flag}')
        
        for country_code in country_dids:
            if len(country_dids[country_code]) < 7:
                continue
            if country_code in ['EU', 'EA']:
                continue
            # turn country code into flag emoji
            flag = chr(0x1F1E6 + ord(country_code[0]) - 65) + chr(0x1F1E6 + ord(country_code[1]) - 65)
            print(country_code, flag)
            country_name = pycountry.countries.get(alpha_2=country_code).name
            create_starterpack(f'#buildinpublic {country_name} {flag}', country_dids[country_code])

        for country_code, count in countries.most_common(20):
            print(f'{country_code} {count}')

        for continent_name, count in continents.most_common():
            print(f'{continent_name} {count}')
    elif args['starter']:
        print(get_starter_pack_members(args['<uri>']))
    elif args['starter-packs']:
        get_all_starter_packs()
