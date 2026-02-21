
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
        # User-Agent を設定して Mojang サーバーに拒否されないようにする
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        if not quiet:
            print(f"  Error downloading {url}: {e}")

def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def setup_minecraft(version_id, username, ram, skip_assets):
    print(f"--- FlashCraft v1.2.1: Setting up Minecraft {version_id} ---")
    
    # 1. Version Manifest
    print("Fetching version manifest...")
    manifest = get_json(MANIFEST_URL)
    version_entry = next((v for v in manifest["versions"] if v["id"] == version_id), None)
    if not version_entry:
        print(f"Error: Version {version_id} not found.")
        return

    v_data = get_json(version_entry["url"])
    
    # 2. JAR and JSON
    version_dir = f"versions/{version_id}"
    client_jar_path = f"{version_dir}/{version_id}.jar"
    client_json_path = f"{version_dir}/{version_id}.json"
    
    print(f"Downloading client JAR and JSON to {version_dir}...")
    download(version_entry["url"], client_json_path)
    download(v_data["downloads"]["client"]["url"], client_jar_path)

    # 3. Libraries
    print("Processing libraries...")
    is_arm = platform.machine() == "aarch64"
    lib_base = "libraries"
    cp_parts = [os.path.abspath(client_jar_path)]

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

        lib_path = None
        if "downloads" in lib:
            if "artifact" in lib["downloads"]:
                art = lib["downloads"]["artifact"]
                lib_path = os.path.join(lib_base, art["path"])
                download(art["url"], lib_path)
            
            # ARM64 LWJGL
            if is_arm and "org.lwjgl" in lib["name"] and "natives-linux" in lib["name"]:
                v = lib["name"].split(":")[-2]
                n = lib["name"].split(":")[1]
                arm_art = f"{n}-{v}-natives-linux-arm64.jar"
                arm_url = f"https://repo1.maven.org/maven2/org/lwjgl/{n}/{v}/{arm_art}"
                arm_path = os.path.join(lib_base, "org/lwjgl", n, v, arm_art)
                download(arm_url, arm_path)
                if os.path.exists(arm_path):
                    lib_path = arm_path
        
        if lib_path:
            cp_parts.append(os.path.abspath(lib_path))

    # 4. Assets
    asset_info = v_data["assetIndex"]
    asset_id = asset_info['id']
    asset_index_path = f"assets/indexes/{asset_id}.json"
    download(asset_info["url"], asset_index_path)

    if not skip_assets:
        with open(asset_index_path, "r") as f:
            assets = json.load(f)
        objects = assets["objects"]
        total = len(objects)
        print(f"Checking {total} assets...")
        count = 0
        for name, info in objects.items():
            h = info["hash"]
            p = os.path.join("assets", "objects", h[:2], h)
            if not os.path.exists(p):
                u = f"https://resources.download.minecraft.net/{h[:2]}/{h}"
                download(u, p, quiet=True)
            count += 1
            if count % 2000 == 0:
                print(f" Progress: {count}/{total}")

    # 5. Launch Script
    print("Generating run.sh...")
    cwd = os.getcwd()
    rel_cp = [os.path.relpath(p, cwd) for p in cp_parts]
    classpath = ":".join(rel_cp)
    
    env = ""
    if is_arm:
        env = "export MESA_GL_VERSION_OVERRIDE=4.5\nexport MESA_GLSL_VERSION_OVERRIDE=450\nexport vblank_mode=0"

    cmd = [
        "java", f"-Xmx{ram}", f"-Xms{ram}",
        "-Djava.library.path=.",
        "-Dlwjgl.util.NoChecks=true",
        "-cp", f"\"{classpath}\"",
        v_data['mainClass'],
        "--username", username,
        "--version", version_id,
        "--gameDir", ".",
        "--assetsDir", "assets",
        "--assetIndex", asset_id,
        "--uuid", "00000000-0000-0000-0000-000000000000",
        "--accessToken", "0",
        "--userType", "mojang",
        "--versionType", "release"
    ]
    
    with open("run.sh", "w") as f:
        f.write("#!/bin/bash\n" + env + "\n")
        f.write(" \\\n    ".join(cmd) + "\n")
    
    os.chmod("run.sh", 0o755)
    print(f"\n✨ FlashCraft Setup Complete! Run ./run.sh")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.21")
    parser.add_argument("--user", default="sktryo")
    parser.add_argument("--ram", default="2G")
    parser.add_argument("--skip-assets", action="store_true")
    args = parser.parse_args()
    setup_minecraft(args.version, args.user, args.ram, args.skip_assets)
