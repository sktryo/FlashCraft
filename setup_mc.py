import json
import os
import sys
import urllib.request
import argparse
import platform
import shutil

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
FABRIC_META_URL = "https://meta.fabricmc.net/v2/versions/loader"

def download(url, path, quiet=False):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not quiet:
        print(f"Downloading: {os.path.basename(path)}")
    try:
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

def setup_minecraft(version_id, username, ram, skip_assets, use_fabric):
    print(f"--- FlashCraft v1.3.0: Setting up Minecraft {version_id} {'(Fabric)' if use_fabric else ''} ---")
    
    # 1. Minecraft Version Data
    print("Fetching Minecraft version manifest...")
    manifest = get_json(MANIFEST_URL)
    version_entry = next((v for v in manifest["versions"] if v["id"] == version_id), None)
    if not version_entry:
        print(f"Error: Minecraft version {version_id} not found.")
        return
    mc_v_data = get_json(version_entry["url"])
    
    # 2. Fabric Loader Data (if requested)
    fabric_data = None
    if use_fabric:
        print(f"Fetching Fabric Loader data for {version_id}...")
        loaders = get_json(f"{FABRIC_META_URL}/{version_id}")
        if not loaders:
            print(f"Error: Fabric not available for {version_id}.")
            return
        loader_version = loaders[0]["loader"]["version"]
        fabric_data = get_json(f"{FABRIC_META_URL}/{version_id}/{loader_version}/profile/json")

    # 3. Base JAR and Libraries
    version_dir = f"versions/{version_id}"
    client_jar_path = f"{version_dir}/{version_id}.jar"
    print(f"Checking Minecraft client JAR...")
    download(mc_v_data["downloads"]["client"]["url"], client_jar_path)

    is_arm = platform.machine() == "aarch64"
    lib_base = "libraries"
    cp_parts = [os.path.abspath(client_jar_path)]

    # --- Process Minecraft Libraries ---
    print("Processing Minecraft libraries...")
    for lib in mc_v_data["libraries"]:
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
            
            if is_arm and "org.lwjgl" in lib["name"] and "natives-linux" in lib["name"]:
                v = lib["name"].split(":")[-2]
                n = lib["name"].split(":")[1]
                arm_art = f"{n}-{v}-natives-linux-arm64.jar"
                arm_url = f"https://repo1.maven.org/maven2/org/lwjgl/{n}/{v}/{arm_art}"
                arm_path = os.path.join(lib_base, "org/lwjgl", n, v, arm_art)
                download(arm_url, arm_path)
                if os.path.exists(arm_path): path = arm_path
            cp_parts.append(os.path.abspath(path))

    # --- Process Fabric Libraries ---
    main_class = mc_v_data['mainClass']
    if use_fabric:
        print("Processing Fabric libraries...")
        main_class = fabric_data["mainClass"]
        for lib in fabric_data["libraries"]:
            name_parts = lib["name"].split(":")
            group = name_parts[0].replace(".", "/")
            name = name_parts[1]
            version = name_parts[2]
            path = os.path.join(lib_base, group, name, version, f"{name}-{version}.jar")
            download(lib["url"] + f"{group}/{name}/{version}/{name}-{version}.jar", path)
            cp_parts.append(os.path.abspath(path))

    # 4. Assets
    asset_info = mc_v_data["assetIndex"]
    asset_id = asset_info['id']
    download(asset_info["url"], f"assets/indexes/{asset_id}.json")
    if not skip_assets:
        print("Checking assets...")
        with open(f"assets/indexes/{asset_id}.json", "r") as f:
            assets = json.load(f)
        objects = assets["objects"]
        count = 0
        for name, info in objects.items():
            h = info["hash"]
            p = os.path.join("assets", "objects", h[:2], h)
            if not os.path.exists(p):
                download(f"https://resources.download.minecraft.net/{h[:2]}/{h}", p, quiet=True)
            count += 1
            if count % 2000 == 0: print(f" Progress: {count}/{len(objects)}")

    # 5. Generate Launch Script
    print("Generating run.sh...")
    cwd = os.getcwd()
    classpath = ":".join([os.path.relpath(p, cwd) for p in cp_parts])
    
    env = ""
    if is_arm:
        env = "export MESA_GL_VERSION_OVERRIDE=4.5\nexport MESA_GLSL_VERSION_OVERRIDE=450\nexport vblank_mode=0"

    # Create mods directory if it doesn't exist
    os.makedirs("mods", exist_ok=True)

    cmd = [
        "java", f"-Xmx{ram}", f"-Xms{ram}",
        "-Djava.library.path=.",
        "-Dlwjgl.util.NoChecks=true",
        "-cp", f"\"{classpath}\"",
        main_class,
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
    print(f"\n✨ FlashCraft Setup Complete! {'(Fabric enabled)' if use_fabric else ''}")
    print(f"📁 Put your mods into the 'mods' folder.")
    print(f"👉 Run: ./run.sh")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FlashCraft: Minecraft ARM64/Fabric Setup Tool")
    parser.add_argument("--version", default="1.21")
    parser.add_argument("--user", default="sktryo")
    parser.add_argument("--ram", default="2G")
    parser.add_argument("--fabric", action="store_true", help="Enable Fabric Loader")
    parser.add_argument("--skip-assets", action="store_true")
    args = parser.parse_args()
    setup_minecraft(args.version, args.user, args.ram, args.skip_assets, args.fabric)