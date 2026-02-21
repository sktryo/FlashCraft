import json
import os
import sys
import urllib.request
import argparse
import platform
import shutil

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

def download(url, path, quiet=False):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not quiet:
        print(f"Downloading: {os.path.basename(path)}")
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        print(f"  Error downloading {url}: {e}")

def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())

def setup_minecraft(version_id, username, ram, skip_assets):
    print(f"--- FlashCraft: Setting up Minecraft {version_id} ---")
    
    # 1. Version Manifest Discovery
    print("Fetching version manifest...")
    manifest = get_json(MANIFEST_URL)
    version_entry = next((v for v in manifest["versions"] if v["id"] == version_id), None)
    if not version_entry:
        print(f"Error: Version {version_id} not found in manifest.")
        return

    v_data = get_json(version_entry["url"])
    
    # 2. Download Game JAR
    client_jar_path = f"versions/{version_id}/{version_id}.jar"
    print(f"Checking client JAR for {version_id}...")
    download(v_data["downloads"]["client"]["url"], client_jar_path)

    # 3. Download Libraries
    print("Processing libraries...")
    is_arm = platform.machine() == "aarch64"
    lib_base = "libraries"
    cp_parts = [client_jar_path]

    for lib in v_data["libraries"]:
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

        if "downloads" in lib and "artifact" in lib["downloads"]:
            art = lib["downloads"]["artifact"]
            path = os.path.join(lib_base, art["path"])
            download(art["url"], path)
            
            # LWJGL ARM64 Swap Logic
            if is_arm and "org.lwjgl" in lib["name"] and "natives-linux" in lib["name"]:
                version = lib["name"].split(":")[-2]
                name = lib["name"].split(":")[1]
                arm64_art = f"{name}-{version}-natives-linux-arm64.jar"
                arm64_url = f"https://repo1.maven.org/maven2/org/lwjgl/{name}/{version}/{arm64_art}"
                arm64_path = os.path.join(lib_base, "org/lwjgl", name, version, arm64_art)
                download(arm64_url, arm64_path)
                path = arm64_path
            
            cp_parts.append(path)

    # 4. Download Assets
    asset_info = v_data["assetIndex"]
    asset_index_id = asset_info['id']
    print(f"Processing assets (index: {asset_index_id})...")
    asset_index_path = f"assets/indexes/{asset_index_id}.json"
    download(asset_info["url"], asset_index_path)

    if not skip_assets:
        with open(asset_index_path, "r") as f:
            assets = json.load(f)
        
        objects = assets["objects"]
        total = len(objects)
        print(f"Downloading {total} assets (this may take a while)...")
        
        count = 0
        for name, info in objects.items():
            hash_str = info["hash"]
            prefix = hash_str[:2]
            url = f"https://resources.download.minecraft.net/{prefix}/{hash_str}"
            path = os.path.join("assets", "objects", prefix, hash_str)
            download(url, path, quiet=True)
            count += 1
            if count % 500 == 0:
                print(f" Progress: {count}/{total}")
        print("Asset processing complete.")
    else:
        print("Skipping asset download as requested.")

    # 5. Generate Launch Script
    print("Generating run.sh...")
    classpath = ":".join(cp_parts)
    env_vars = ""
    if is_arm:
        env_vars = "export MESA_GL_VERSION_OVERRIDE=4.5\nexport MESA_GLSL_VERSION_OVERRIDE=450\nexport vblank_mode=0\n"

    run_script = f"""#!/bin/bash
{env_vars}
java -Xmx{ram} -Xms{ram} \\
    -Djava.library.path=. \\
    -Dlwjgl.util.NoChecks=true \\
    -cp "{classpath}" \\
    {v_data['mainClass']} \\
    --username {username} \\
    --version {version_id} \\
    --gameDir . \\
    --assetsDir assets \\
    --assetIndex {asset_index_id} \\
    --uuid 00000000-0000-0000-0000-000000000000 \\
    --accessToken 0 \\
    --userType mojang \\
    --versionType release
"""
    with open("run.sh", "w") as f:
        f.write(run_script)
    os.chmod("run.sh", 0o755)
    
    print(f"\n✨ FlashCraft: Setup complete for {version_id}!")
    print(f"🚀 User: {username} | RAM: {ram}")
    print("👉 Run './run.sh' to start the game.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FlashCraft: Minecraft ARM64 Setup Tool")
    parser.add_argument("--version", default="1.21", help="Minecraft version (default: 1.21)")
    parser.add_argument("--user", default="sktryo", help="Username (default: sktryo)")
    parser.add_argument("--ram", default="2G", help="RAM allocation (default: 2G)")
    parser.add_argument("--skip-assets", action="store_true", help="Skip downloading assets")
    args = parser.parse_args()
    
    setup_minecraft(args.version, args.user, args.ram, args.skip_assets)