#! /usr/bin/env python

"""
Usage:
    do.py replies [--stats]
    do.py starter <uri>
    do.py update-starterpacks
    do.py get-starterpacks <did>
    do.py get-starterpack-members <uri>
    do.py get-post <uri>
do.py replies                       - pull replies from bluesky - look at the country flag and add them to starterpacks
do.py starter <uri>                 - get the members of a starterpack
do.py update-starterpacks           - update the starterpacks.json file with the members added manually via the web interface
do.py get-starterpacks <did>        - get all starterpacks for a given user
do.py get-starterpack-members <uri> - get the members of a starterpack
"""

from atproto import Client
import emoji
import requests
from docopt import docopt
import datetime
import pycountry_convert
from collections import Counter
from collections import defaultdict
import json
import os
import pycountry
import time
from joblib import Memory

MAX_BEARER_AGE = 3600

CURRENT_USER_DID = 'did:plc:cv7n7pa4fmtkgyzfl2rf4xn3'

POST_URIS = [
    f'at://{CURRENT_USER_DID}/app.bsky.feed.post/3lbodzewg4k2l',
    f'at://{CURRENT_USER_DID}/app.bsky.feed.post/3lbtocclctc2v',
    f'at://{CURRENT_USER_DID}/app.bsky.feed.post/3lbwdvxqmg22i',
    f'at://{CURRENT_USER_DID}/app.bsky.feed.post/3lc5ukgpbfs2r',
]

memory = Memory(location='.cache', verbose=0)

def _name(country_iso):
    country_name = pycountry.countries.get(alpha_2=country_iso).name
    flag = chr(0x1F1E6 + ord(country_iso[0]) - 65) + chr(0x1F1E6 + ord(country_iso[1]) - 65)
    return f'#buildinpublic {country_name} {flag}'

@memory.cache
def get_post_mentions(post_uri):
    client = Client()
    client.login(os.getenv('BLUESKY_USERNAME'), os.getenv('BLUESKY_PASSWORD'))
    post = client.get_post_thread(post_uri)
    members = []
    try:
        for facet in post['thread']['post']['record']['facets']:
            members.append(facet['features'][0]['did'])
    except KeyError:
        pass
    return members

def get_all_starter_packs(did=CURRENT_USER_DID):
    from atproto import models
    client = Client()
    client.login(os.getenv('BLUESKY_USERNAME'), os.getenv('BLUESKY_PASSWORD'))
    params = models.AppBskyGraphGetActorStarterPacks.Params(actor=did)
    res = client.app.bsky.graph.get_actor_starter_packs(params)
    for i in res['starter_packs']:
        name = i['record']['name']
        uri = i['uri']
        print(name, uri)
    return res

@memory.cache
def get_starter_pack_members(uri):
    from atproto import models
    client = Client()
    client.login(os.getenv('BLUESKY_USERNAME'), os.getenv('BLUESKY_PASSWORD'))
    params = models.AppBskyGraphGetStarterPack.Params(starter_pack=uri)
    res = client.app.bsky.graph.get_starter_pack(params)
    list_uri = res['starter_pack']['record']['list']
    starter_pack_created_at = res['starter_pack']['record']['created_at']
    params = models.AppBskyGraphGetList.Params(list=list_uri)
    list = client.app.bsky.graph.get_list(params)
    return [l['subject']['did'] for l in list['items']], list_uri, starter_pack_created_at

def get_cached_post_thread(post_uri):
    client = Client()
    client.login(os.getenv('BLUESKY_USERNAME'), os.getenv('BLUESKY_PASSWORD'))
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
    base_url = "https://amanita.us-east.host.bsky.network/xrpc"
    headers = get_headers()

    created_at = datetime.datetime.utcnow().isoformat() + "Z"
    
    # Step 1: Create the list
    create_list_data = {
        "collection": "app.bsky.graph.list",
        "repo": CURRENT_USER_DID,
        "record": {
            "name": name,
            "createdAt": created_at,
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
    starterpack_created_at = datetime.datetime.utcnow().isoformat() + "Z"
    starterpack_data = {
        "collection": "app.bsky.graph.starterpack",
        "repo": CURRENT_USER_DID,
        "record": {
            "name": name,
            "list": list_uri,
            "feeds": [],
            "createdAt": starterpack_created_at,
            "$type": "app.bsky.graph.starterpack"
        }
    }
    
    response = requests.post(f"{base_url}/com.atproto.repo.createRecord", 
                           headers=headers, 
                           json=starterpack_data)
    response.raise_for_status()
    starter_pack_uri = response.json()['uri']
    
    return starter_pack_uri, list_uri, starterpack_created_at

def emoji_to_code(flag_emoji):
    # Convert the flag emoji to the regional indicator letters
    codes = [c for c in flag_emoji]
    # Convert the regional indicator symbols to regular letters
    country_code = ''.join(chr(ord(c) - 127397) for c in codes)
    return country_code

def country_code_from_emoji(char):
    # Method 1: Check for regional indicator symbols (most country flags)
    country_iso = None
    if len(char) == 2 and all(0x1F1E6 <= ord(c) <= 0x1F1FF for c in char):
        country_iso = emoji_to_code(char)
    
    # Method 2: Check for other special flag emojis
    if emoji.demojize(char).startswith(':flag_'):
        country_code = emoji.demojize(char)[6:]
        country_iso = emoji_to_code(country_code)
    
    if country_iso in ['EU', 'EA']:
        return None
    else:
        return country_iso

def update_starterpacks():
    # loop through all starterpacks in starterpacks.json
    with open('starterpacks.json', 'r') as f:
        starterpacks = json.load(f)
    for country_iso in starterpacks:
        print(f'Updating {country_iso}')
        members, list_uri, starter_pack_created_at = get_starter_pack_members(starterpacks[country_iso]['uri'])
        starterpacks[country_iso] = dict(
            name=starterpacks[country_iso]['name'],
            uri=starterpacks[country_iso]['uri'],
            members=sorted(members),
            list_uri=list_uri,
            created_at=starter_pack_created_at
        )
        print(f'{len(members)} members')
    with open('starterpacks.json', 'w') as f:
        json.dump(starterpacks, f, indent=2)

def create_or_update_starter_pack(*, country_iso, members):
    # check if country_iso is in starterpacks.json
    with open('starterpacks.json', 'r') as f:
        starterpacks = json.load(f)
    
    # deduplicate members
    members = list(set(members))

    if country_iso in starterpacks:
        for member in members:
            if member not in starterpacks[country_iso]['members']:
                print(f'Adding {member} to {country_iso}')
                add_profile_to_starter_pack(member, starterpacks[country_iso]['list_uri'], starterpacks[country_iso]['uri'], starterpacks[country_iso]['name'], starterpacks[country_iso]['created_at'])
        starterpacks[country_iso]['members'] = sorted(members)
    else:
        name = _name(country_iso)
        print(f'Creating {name} with {len(members)} members')
        starter_pack_uri, list_uri, starterpack_created_at = create_starterpack(name, members)
        starterpacks[country_iso] = dict(
            name=name,
            uri=starter_pack_uri,
            members=sorted(members),
            list_uri=list_uri,
            created_at=starterpack_created_at
        )
    with open('starterpacks.json', 'w') as f:
        json.dump(starterpacks, f, indent=2)
    
def get_headers():
    import json
    if os.path.exists('bsky-curl.txt') and os.path.getmtime('bsky-curl.txt') > time.time() - MAX_BEARER_AGE:
        content = open('bsky-curl.txt').read()
    else:
        raise Exception("Bearer token is too old")

    headers = {}
    for line in content.split('\n'):
        if line.startswith('curl'):
            continue
        # get part between ' and '
        line = line.split("'")[1]
        key, value = line.split(': ')
        headers[key] = value

    return headers

def add_profile_to_starter_pack(profile_uri: str, list_uri: str, starter_pack_uri: str, name: str, created_at: str):
    """
    Add a profile to an existing starter pack and update the starter pack record.
    
    Args:
        profile_uri: The DID of the profile to add
        list_uri: The URI of the list
        starter_pack_uri: The URI of the starter pack
        name: The name of the starter pack
        created_at: The original creation timestamp
    """
    
    base_url = "https://amanita.us-east.host.bsky.network/xrpc"
    headers = get_headers()
    
    # Step 1: Add user to the list
    current_time = datetime.datetime.utcnow().isoformat() + "Z"
    apply_writes_data = {
        "repo": CURRENT_USER_DID,
        "writes": [{
            "$type": "com.atproto.repo.applyWrites#create",
            "collection": "app.bsky.graph.listitem",
            "value": {
                "$type": "app.bsky.graph.listitem",
                "subject": profile_uri,
                "list": list_uri,
                "createdAt": current_time
            }
        }]
    }
    
    response = requests.post(f"{base_url}/com.atproto.repo.applyWrites", 
                           headers=headers, 
                           json=apply_writes_data)
    response.raise_for_status()
    
    # Step 2: Update the starter pack record
    rkey = starter_pack_uri.split('/')[-1]
    put_record_data = {
        "repo": CURRENT_USER_DID,
        "collection": "app.bsky.graph.starterpack",
        "rkey": rkey,
        "record": {
            "name": name,
            "list": list_uri,
            "feeds": [],
            "createdAt": created_at,
            "updatedAt": current_time
        }
    }
    
    response = requests.post(f"{base_url}/com.atproto.repo.putRecord", 
                           headers=headers, 
                           json=put_record_data)
    response.raise_for_status()

if __name__ == "__main__":
    import os
    import dotenv
    dotenv.load_dotenv()

    args = docopt(__doc__)

    if args['replies']:
        # check if bsky-curl.txt is too old and fail early
        if os.path.getmtime('bsky-curl.txt') < time.time() - MAX_BEARER_AGE:
            raise Exception("Bearer token is too old")
        countries = Counter()
        continents = Counter()

        country_dids = defaultdict(list)

        # sideload some starterpacks
        sideload_starterpacks = [
            ('CN', 'at://did:plc:nhsoiitzsxouxhs7ptflqjib/app.bsky.graph.starterpack/3lbyynkaqqz2k'),
            ('IT', 'at://did:plc:l2ermhmovacku4iikta656zf/app.bsky.graph.starterpack/3lbx4piaquc2j'),
            ('NL', 'at://did:plc:nhlv6mfdlcca4ihm65zcdbc3/app.bsky.graph.starterpack/3lbri25eh222e'),
        ]

        for country_iso, starterpack_uri in sideload_starterpacks:
            members, list_uri, starter_pack_created_at = get_starter_pack_members(starterpack_uri)
            country_dids[country_iso] = members
        
        # sideload from posts
        sideload_posts = [
            ('DK', 'at://did:plc:52rfaxvrz6wij3cwkifh3ut7/app.bsky.feed.post/3lbu2sk5pur2s'),
            ('LT', 'at://did:plc:4emx4cti65cwfm2qzuqk7svn/app.bsky.feed.post/3lbwwvbaisk2w'),
            ('TH', 'at://did:plc:egcl3ocfzkrmsp6j76xopowd/app.bsky.feed.post/3lc7qsfzvw223'),
        ]
        for country_iso, post_uri in sideload_posts:
            dids = list(get_post_mentions(post_uri))
            country_dids[country_iso] = dids

        for post_uri in POST_URIS:
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
                
                # if did == 'did:plc:iyjda5z632gdbjgmotr6e55c':
                #     print(text_original)
        total = 0
        for country_code in country_dids:
            if len(country_dids[country_code]) < 7:
                continue
            country_name = _name(country_code)
            create_or_update_starter_pack(country_iso=country_code, members=country_dids[country_code])
            total += len(country_dids[country_code])
        
        print(f'total: {total}')

        if args['--stats']:
            starterpacks = json.load(open('starterpacks.json'))
            starterpack_info_uris = []
            for country_code, count in countries.most_common():
                flag = chr(0x1F1E6 + ord(country_code[0]) - 65) + chr(0x1F1E6 + ord(country_code[1]) - 65)
                try:
                    country_name = pycountry.countries.get(alpha_2=country_code).name
                    if country_code in starterpacks:
                        uri = starterpacks[country_code]['uri']
                        id = uri.split('/')[-1]
                        url = f'https://bsky.app/starter-pack/{CURRENT_USER_DID}/{id}'
                        starterpack_info_uris.append(f'{country_name} {flag} {url}')
                except AttributeError:
                    print(f'{country_code} not found')
                    continue
                print(f'{flag} {count}')
            for continent_name, count in continents.most_common():
                print(f'{continent_name} {count} {100.0 * count / total:.1f}%')
            for starterpack_uri in starterpack_info_uris:
                print(starterpack_uri)
    elif args['starter']:
        print(get_starter_pack_members(args['<uri>']))
    elif args['update-starterpacks']:
        update_starterpacks()
    elif args['get-starterpacks']:
        packs = get_all_starter_packs(args['<did>'])
        for pack in packs['starter_packs']:
            print(pack['record']['name'], pack['uri'])
    elif args['get-starterpack-members']:
        members, list_uri, starter_pack_created_at = get_starter_pack_members(args['<uri>'])
        print(members)
    elif args['get-post']:
        mentions = list(get_post_mentions(args['<uri>']))
        print(mentions)
