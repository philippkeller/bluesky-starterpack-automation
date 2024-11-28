# Bluesky Starterpack Automation

Code to automate per-country starterpacks in Bluesky.

See Starterpacks at https://bsky.app/profile/philippkeller.com

## Usage

### Starter pack automation

Bluesky API doesn't support starterpack automation yet, that's why we need to mimick the browser request.

1. Go to Bluesky
2. Open dev tools, network tab
3. Click on "Notifications"
4. Look for the `app.bsky.notification.listNotifications` request
5. Copy as cURL
6. Save it as `bsky-curl.txt`

### Bluesky API

For pulling bluesky replies the script uses the normal Bluesky API.

1. create the file `.env`
2. add your normal bluesky username/password as `BLUESKY_USERNAME` and `BLUESKY_PASSWORD`

### Adapting the script

Before you start it you'd want to change:

1. CURRENT_USER_DID - go to your profile page, view source, find the `did`
2. POST_URIS - add the uris of the posts from which you want to pull replies

### Running the script

Then you can use the `do.py replies` script to add replies to the starterpack.