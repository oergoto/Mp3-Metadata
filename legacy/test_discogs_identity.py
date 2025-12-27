import requests

DISCOGS_TOKEN = "kdnqlxPvFHoiEzsyfYdwowLPzVcOFOKvrWVSSSJG"
USER_AGENT = "MP3-Metadata-Pipeline/1.0 (oergoto@gmail.com)"

url = "https://api.discogs.com/oauth/identity"
headers = {
    "Authorization": f"Discogs token={DISCOGS_TOKEN}",
    "User-Agent": USER_AGENT,
}

resp = requests.get(url, headers=headers, timeout=30)

print("Status code:", resp.status_code)
print("Body:")
print(resp.text)