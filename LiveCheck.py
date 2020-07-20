import urllib.request
import urllib.error
import requests
import json
from authlib.integrations.requests_client import OAuth2Session


def get_access_token():
    authorize_url = "https://id.twitch.tv/oauth2/authorize"

    # callback url specified when the application was defined
    callback_uri = "http://localhost:28888"

    # client (application) credentials
    client_id = '301fbt6wgu2wzn7f6s3js7t7nyaze1'
    client_secret = 'pevv0t36avp0ed85xbxmoo4l244qes'

    client = OAuth2Session(client_id, client_secret, redirect_uri=callback_uri)

    uri, state = client.create_authorization_url(authorize_url, response_type='token')

    authorization_response = \
        'http://localhost:28888/#access_token=3awghb844sdbusoig8kwc24w80an0q&scope=&token_type=bearer'
    token = client.fetch_token(authorization_response=authorization_response)
    return token


def liveCheck(chan_name):
    try:
        tokenInfo = get_access_token()
        authorization = "Bearer " + tokenInfo['access_token']
        url = f"https://api.twitch.tv/helix/streams?user_login={chan_name}"
        heading = {
            "Client-ID": "301fbt6wgu2wzn7f6s3js7t7nyaze1",
            "Authorization": authorization
        }
        req = urllib.request.Request(url, headers=heading)
        response = urllib.request.urlopen(req)
        output = json.loads(response.read())
        output = output["data"]
        for i in output:
            output = i
        if "type" in output:
            return True
        else:
            return False
    except Exception as e:
        print('gettwitchapi', e)
        return e

# liveCheck("TheGreatGildersneeze")
