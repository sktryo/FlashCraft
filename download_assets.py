import json
import os
import urllib.request

def download(url, path):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        print(f"  Error downloading {url}: {e}")

def main():
    with open("client.json", "r") as f:
        data = json.load(f)

    asset_index_info = data["assetIndex"]
    index_name = asset_index_info["id"]
    index_url = asset_index_info["url"]
    
    print(f"Fetching asset index: {index_name}")
    index_path = os.path.join("assets", "indexes", f"{index_name}.json")
    download(index_url, index_path)
    
    with open(index_path, "r") as f:
        assets = json.load(f)
    
    objects = assets["objects"]
    total = len(objects)
    print(f"Downloading {total} assets...")
    
    count = 0
    for name, info in objects.items():
        hash_str = info["hash"]
        prefix = hash_str[:2]
        url = f"https://resources.download.minecraft.net/{prefix}/{hash_str}"
        path = os.path.join("assets", "objects", prefix, hash_str)
        download(url, path)
        count += 1
        if count % 500 == 0:
            print(f" Progress: {count}/{total}")

    print("\nAsset download complete.")

if __name__ == "__main__":
    main()