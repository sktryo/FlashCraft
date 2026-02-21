
import json
import os
import urllib.request

def download(url, path):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"Downloading: {os.path.basename(path)}")
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        print(f"  Error downloading {url}: {e}")

def main():
    with open("client.json", "r") as f:
        data = json.load(f)

    base_dir = "libraries"
    
    # 1. 共通ライブラリのダウンロード
    for lib in data["libraries"]:
        # OSルールチェック (linuxかどうか)
        allow = True
        if "rules" in lib:
            allow = False
            for rule in lib["rules"]:
                if rule["action"] == "allow":
                    if "os" not in rule or rule["os"]["name"] == "linux":
                        allow = True
                elif rule["action"] == "disallow":
                    if "os" in rule and rule["os"]["name"] == "linux":
                        allow = False
        
        if not allow:
            continue

        # ダウンロード実行
        if "downloads" in lib and "artifact" in lib["downloads"]:
            artifact = lib["downloads"]["artifact"]
            path = os.path.join(base_dir, artifact["path"])
            download(artifact["url"], path)
        
        # LWJGLのネイティブライブラリ処理 (aarch64用への差し替え)
        if "org.lwjgl" in lib["name"] and "natives-linux" in lib["name"]:
            # 公式はx86_64なので、Maven Centralからarm64用を推測して取得を試みる
            # 例: org.lwjgl:lwjgl:3.3.3:natives-linux -> natives-linux-arm64
            version = lib["name"].split(":")[-2]
            name = lib["name"].split(":")[1]
            arm64_artifact = f"{name}-{version}-natives-linux-arm64.jar"
            arm64_url = f"https://repo1.maven.org/maven2/org/lwjgl/{name}/{version}/{arm64_artifact}"
            arm64_path = os.path.join(base_dir, "org/lwjgl", name, version, arm64_artifact)
            download(arm64_url, arm64_path)

    print("\nLibrary download complete.")

if __name__ == "__main__":
    main()
