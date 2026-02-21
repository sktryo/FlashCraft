
import json
import os
import sys
import urllib.request
import argparse
import platform
import shutil

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

def download(url, path):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"Downloading: {os.path.basename(path)}")
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        print(f"  Error: {e}")

def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())

def setup_minecraft(version_id, username, ram):
    print(f"--- Setting up Minecraft {version_id} ---")
    
    # 1. バージョン情報の取得
    manifest = get_json(MANIFEST_URL)
    version_entry = next((v for v in manifest["versions"] if v["id"] == version_id), None)
    if not version_entry:
        print(f"Version {version_id} not found.")
        return

    v_data = get_json(version_entry["url"])
    
    # 2. client.jar のダウンロード
    client_jar_path = f"versions/{version_id}/{version_id}.jar"
    download(v_data["downloads"]["client"]["url"], client_jar_path)

    # 3. ライブラリのダウンロード
    is_arm = platform.machine() == "aarch64"
    lib_base = "libraries"
    cp_parts = [client_jar_path]

    for lib in v_data["libraries"]:
        # OSルールのチェック
        allow = True
        if "rules" in lib:
            allow = False
            for rule in lib["rules"]:
                action = rule["action"]
                if "os" in rule:
                    if rule["os"]["name"] == "linux" and action == "allow": allow = True
                    if rule["os"]["name"] == "linux" and action == "disallow": allow = False
                else:
                    if action == "allow": allow = True
        if not allow: continue

        # 通常のアーティファクト
        if "downloads" in lib and "artifact" in lib["downloads"]:
            art = lib["downloads"]["artifact"]
            path = os.path.join(lib_base, art["path"])
            download(art["url"], path)
            
            # LWJGL ARM64 差し替えロジック
            if is_arm and "org.lwjgl" in lib["name"] and "natives-linux" in lib["name"]:
                version = lib["name"].split(":")[-2]
                name = lib["name"].split(":")[1]
                arm64_art = f"{name}-{version}-natives-linux-arm64.jar"
                arm64_url = f"https://repo1.maven.org/maven2/org/lwjgl/{name}/{version}/{arm64_art}"
                arm64_path = os.path.join(lib_base, "org/lwjgl", name, version, arm64_art)
                download(arm64_url, arm64_path)
                path = arm64_path
            
            cp_parts.append(path)

    # 4. アセットのダウンロード (軽量化のため一部のみ、あるいはインデックスのみ取得)
    asset_info = v_data["assetIndex"]
    asset_index_path = f"assets/indexes/{asset_info['id']}.json"
    download(asset_info["url"], asset_index_path)
    # ※ 本来はここで全アセットを回すべきだが、今回は時間短縮のため省略。
    # 実際は download_assets.py のロジックをここに統合可能。

    # 5. 起動スクリプトの生成
    classpath = ":".join(cp_parts)
    # RPi向けの環境変数
    env_vars = ""
    if is_arm:
        env_vars = "export MESA_GL_VERSION_OVERRIDE=4.5
export MESA_GLSL_VERSION_OVERRIDE=450
export vblank_mode=0
"

    run_script = f"""#!/bin/bash
{env_vars}
java -Xmx{ram} -Xms{ram} 
    -Djava.library.path=. 
    -Dlwjgl.util.NoChecks=true 
    -cp "{classpath}" 
    {v_data['mainClass']} 
    --username {username} 
    --version {version_id} 
    --gameDir . 
    --assetsDir assets 
    --assetIndex {asset_info['id']} 
    --uuid 00000000-0000-0000-0000-000000000000 
    --accessToken 0 
    --userType mojang 
    --versionType release
"""
    with open("run.sh", "w") as f:
        f.write(run_script)
    os.chmod("run.sh", 0o755)
    print(f"
Setup complete for {version_id}!")
    print("Run './run.sh' to start.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.21", help="Minecraft version")
    parser.add_argument("--user", default="sktryo", help="Username")
    parser.add_argument("--ram", default="2G", help="RAM allocation (e.g. 2G)")
    args = parser.parse_args()
    
    setup_minecraft(args.version, args.user, args.ram)
