#! /usr/bin/env python

from atproto import Client
import emoji
import requests
from docopt import docopt

"""
Usage:
    do.py add-user-to-starterpack <actor_did>
    do.py replies
"""

def add_user_to_starterpack(actor_did: str, bearer_token: str) -> dict:
    """
    Fetch a user's profile from Bluesky using the app.bsky.actor.getProfile endpoint.
    
    Args:
        actor_did (str): The DID of the user to fetch
        bearer_token (str): The authentication token
        
    Returns:
        dict: The JSON response from the API
    """
    url = f"https://amanita.us-east.host.bsky.network/xrpc/app.bsky.actor.getProfile"
    
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'atproto-accept-labelers': 'did:plc:ar7c4by46qjdydhdevvrndac;redact',
        'authorization': f'Bearer {bearer_token}',
        'origin': 'https://bsky.app',
        'priority': 'u=1, i',
        'referer': 'https://bsky.app/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    
    params = {
        'actor': actor_did
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()  # Raise an exception for bad status codes
    
    return response.json()

if __name__ == "__main__":
    import os
    import dotenv
    dotenv.load_dotenv()

    args = docopt(__doc__)

    if args['add-user-to-starterpack']:
        add_user_to_starterpack(args['<actor_did>'], os.getenv('BSKY_BEARER_TOKEN'))
    elif args['replies']:
        client = Client()
        # read password from .env file: BSKY_PASSWORD
        client.login('philippkeller.com', os.getenv('BSKY_PASSWORD'))

        # go to post, view source and look for at://…
        post_uri = 'at://did:plc:cv7n7pa4fmtkgyzfl2rf4xn3/app.bsky.feed.post/3lbodzewg4k2l'
        post = client.get_post_thread(post_uri)
        replies = [item['post']['record']['text'] for item in post['thread']['replies']]
        flags = [emoji.emoji_list(reply)[0]['emoji'] for reply in replies if emoji.emoji_list(reply)]
        print("".join(flags))