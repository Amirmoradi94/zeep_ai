import requests

url = "https://www.searchapi.io/api/v1/search"
params = {
  "engine": "google_light",
  "q": "black shirt zara",
  "api_key": "W6YatFWJgDRH8RoLnWL1yQm7"
}

response = requests.get(url, params=params)
print(response.text)
