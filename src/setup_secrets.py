import os
import json

def setup_secrets():
    # client_secret.json oluştur
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET_JSON")
    if client_secret:
        with open("client_secret.json", "w") as f:
            f.write(client_secret)
        print("client_secret.json (JSON secret'tan) oluşturuldu.")
    else:
        cid = os.getenv("YOUTUBE_CLIENT_ID")
        csec = os.getenv("YOUTUBE_CLIENT_SECRET")
        if cid and csec:
            client_secret_data = {
                "installed": {
                    "client_id": cid,
                    "client_secret": csec,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
                }
            }
            with open("client_secret.json", "w") as f:
                json.dump(client_secret_data, f)
            print("client_secret.json (YOUTUBE_CLIENT_ID ve YOUTUBE_CLIENT_SECRET secret'larından) oluşturuldu.")

    # token.json oluştur
    youtube_token = os.getenv("YOUTUBE_TOKEN_JSON")
    if youtube_token:
        with open("token.json", "w") as f:
            f.write(youtube_token)
        print("token.json oluşturuldu.")

if __name__ == "__main__":
    setup_secrets()
