
import json
import os
import sys
import urllib.request # Keep for get_json for now, might switch to requests fully
import argparse
import platform
import shutil
import time
import random # For exponential backoff
from concurrent.futures import ThreadPoolExecutor, as_completed # For parallel downloads

# --- Try to import requests, if not available, print message ---
try:
    import requests
except ImportError:
    print("Warning: 'requests' library not found. Falling back to urllib.request for downloads.")
    print("         For more robust downloads, please install it: pip install requests")
    requests = None # Set to None if not available

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
FABRIC_META_URL = "https://meta.fabricmc.net/v2/versions/loader"

# Improved User-Agent to avoid blocking
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

# Number of parallel download threads (default)
DEFAULT_MAX_DOWNLOAD_WORKERS = 8 

def download_file_with_retries(url, path, quiet=True, retries=5, initial_delay=1, timeout=30):
    os.makedirs(os.path.dirname(path), exist_ok=True) # Ensure dir exists before any attempt

    if requests: # Use requests if available
        for attempt in range(retries):
            try:
                headers = {'User-Agent': DEFAULT_USER_AGENT}
                response = requests.get(url, headers=headers, stream=True, timeout=timeout)
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

                with open(path, 'wb') as out_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        out_file.write(chunk)
                response.close() # Close connection explicitly
                return True
            except requests.exceptions.RequestException as e:
                if not quiet:
                    sys.stderr.write(f"\n  Attempt {attempt + 1}/{retries} failed for {os.path.basename(path)} (URL: {url}): {e}\n")
                    if "text/html" in response.headers.get('Content-Type', ''):
                        sys.stderr.write(f"  Warning: Server returned HTML content, likely a redirect or error page.\n")
                if attempt < retries - 1:
                    delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
                    if not quiet:
                        sys.stderr.write(f"  Retrying in {delay:.1f} seconds...\n")
                    time.sleep(delay)
                else:
                    if not quiet:
                        sys.stderr.write(f"  Failed to download {os.path.basename(path)} (URL: {url}) after {retries} attempts.\n")
                    return False
        return False # Should not be reached
    else: # Fallback to urllib.request
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
                with urllib.request.urlopen(req, timeout=timeout) as response, open(path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
                return True # Download successful
            except urllib.error.URLError as e:
                if not quiet:
                    sys.stderr.write(f"\n  Attempt {attempt + 1}/{retries} failed for {os.path.basename(path)} (URL: {url}): {e}\n")
                if attempt < retries - 1:
                    delay = initial_delay * (2 ** attempt) + random.uniform(0, 1) # Exponential backoff with jitter
                    if not quiet:
                        sys.stderr.write(f"  Retrying in {delay:.1f} seconds...\n")
                    time.sleep(delay)
                else: # Last attempt failed
                    if not quiet:
                        sys.stderr.write(f"  Failed to download {os.path.basename(path)} (URL: {url}) after {retries} attempts.\n")
                    return False
            except Exception as e:
                if not quiet:
                    sys.stderr.write(f"\n  Unexpected error during download of {os.path.basename(path)} (URL: {url}): {e}\n")
                return False # No retry for unexpected errors
        return False # Should not be reached

def download(url, path, quiet=False, retries=5, initial_delay=1, timeout=30):
    if os.path.exists(path):
        return True # File already exists, consider it successful
    
    if not quiet:
        sys.stderr.write(f"Downloading: {os.path.basename(path)}\n")
    return download_file_with_retries(url, path, quiet=quiet, retries=retries, initial_delay=initial_delay, timeout=timeout)

def get_json(url, timeout=30):
    if requests: # Use requests for JSON if available
        headers = {'User-Agent': DEFAULT_USER_AGENT}
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            sys.stderr.write(f"\n  Error fetching JSON from {url}: {e}\n")
            return None
    else: # Fallback to urllib.request
        try:
            req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.URLError as e:
            sys.stderr.write(f"\n  Error fetching JSON from {url}: {e}\n")
            return None

def setup_minecraft(version_id, username, ram, skip_assets, use_fabric, config_name, max_workers):
    print(f"--- FlashCraft v1.9.2: Setting up Minecraft {version_id} {'(Fabric)' if use_fabric else ''} ---")
    
    # 1. Minecraft Version Data
    print("Fetching Minecraft version manifest...")
    manifest = get_json(MANIFEST_URL)
    if manifest is None:
        print("Error: Could not fetch Minecraft version manifest. Check network connection.")
        return
    version_entry = next((v for v in manifest["versions"] if v["id"] == version_id), None)
    if not version_entry:
        print(f"Error: Minecraft version {version_id} not found.")
        return
    mc_v_data = get_json(version_entry["url"])
    if mc_v_data is None:
        print(f"Error: Could not fetch Minecraft version data for {version_id}. Check network connection.")
        return
    
    # 2. Fabric Loader Data (if requested)
    fabric_data = None
    if use_fabric:
        print(f"Fetching Fabric Loader data for {version_id}...")
        loaders = get_json(f"{FABRIC_META_URL}/{version_id}")
        if loaders is None:
            print("Error: Could not fetch Fabric Loader data. Check network connection or Fabric Meta API status.")
            return
        if not loaders:
            print(f"Error: Fabric not available for {version_id}.")
            return
        # Use latest stable loader version
        loader_version = next((l["loader"]["version"] for l in loaders if not l["loader"]["stable"]), loaders[0]["loader"]["version"])
        fabric_data = get_json(f"{FABRIC_META_URL}/{version_id}/{loader_version}/profile/json")
        if fabric_data is None:
            print(f"Error: Could not fetch Fabric profile data for {version_id}/{loader_version}. Check network connection or Fabric Meta API status.")
            return

    # 3. Base JAR and Libraries
    version_dir = f"versions/{version_id}"
    client_jar_path = f"{version_dir}/{version_id}.jar"
    print(f"Checking Minecraft client JAR...")
    if not download(mc_v_data["downloads"]["client"]["url"], client_jar_path, quiet=False):
        print("  Client JAR download failed. Aborting setup.")
        return

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

        lib_path = None
        if "downloads" in lib:
            if "artifact" in lib["downloads"]:
                art = lib["downloads"]["artifact"]
                lib_path = os.path.join(lib_base, art["path"])
                if not download(art["url"], lib_path, quiet=True): # Quiet download for libraries
                    sys.stderr.write(f"\n  Warning: Failed to download library {lib['name']}. Setup may fail.\n")
                    lib_path = None # Don't add to classpath if download failed
            
            # ARM64 LWJGL
            if is_arm and "org.lwjgl" in lib["name"] and "natives-linux" in lib["name"]:
                name_parts_full = lib["name"].split(":")
                group_name = name_parts_full[0]
                artifact_name = name_parts_full[1]
                version_str = name_parts_full[2]
                
                arm_art = f"{artifact_name}-{version_str}-natives-linux-arm64.jar"
                arm_url = f"https://repo1.maven.org/maven2/{group_name.replace('.', '/')}/{artifact_name}/{version_str}/{arm_art}"
                arm_path = os.path.join(lib_base, group_name.replace('.', '/'), artifact_name, version_str, arm_art)
                
                if download(arm_url, arm_path, quiet=True): # Quiet download for libraries
                    lib_path = arm_path # Override with ARM64 version
                else:
                    sys.stderr.write(f"\n  Warning: Failed to download ARM64 LWJGL native {lib['name']}. Setup may fail.\n")
        
        if lib_path:
            cp_parts.append(os.path.abspath(lib_path))

    # --- Process Fabric Libraries ---
    main_class = mc_v_data['mainClass']
    if use_fabric:
        print("Processing Fabric libraries...")
        main_class = fabric_data["mainClass"]
        for lib in fabric_data["libraries"]:
            name_parts = lib["name"].split(":")
            group_path = name_parts[0].replace(".", "/")
            artifact_name = name_parts[1]
            version = name_parts[2]
            
            local_path = os.path.join(lib_base, group_path, artifact_name, version, f"{artifact_name}-{version}.jar")
            if not download(lib["url"], local_path, quiet=True): # Quiet download for libraries
                sys.stderr.write(f"\n  Warning: Failed to download Fabric library {lib['name']}. Setup may fail.\n")
            cp_parts.append(os.path.abspath(local_path))

    # 4. Assets
    asset_info = mc_v_data["assetIndex"]
    asset_id = asset_info['id']
    if not download(asset_info["url"], f"assets/indexes/{asset_id}.json", quiet=False):
        print("  Asset index download failed. Skipping asset download.")
        skip_assets = True # Force skip if index fails

    # --- Asset Download Progress (Parallel) ---
    if not skip_assets:
        print("Calculating asset download requirements...")
        with open(f"assets/indexes/{asset_id}.json", "r") as f:
            assets = json.load(f)
        objects = assets["objects"]
        
        assets_to_download = []
        total_bytes_to_download = 0
        for name, info in objects.items():
            h = info["hash"]
            p = os.path.join("assets", "objects", h[:2], h)
            if not os.path.exists(p):
                assets_to_download.append({'hash': h, 'path': p, 'size': info['size'], 'url': f"https://resources.download.minecraft.net/{h[:2]}/{h}"})
                total_bytes_to_download += info['size']
        
        num_assets_to_download = len(assets_to_download)
        total_assets_in_index = len(objects) # Total assets in the index, regardless of if they need download

        if num_assets_to_download == 0:
            print("All assets already downloaded.")
        else:
            print(f"Downloading {num_assets_to_download} of {total_assets_in_index} assets ({total_bytes_to_download / (1024*1024):.2f} MB) using {max_workers} workers...")
            
            start_time = time.time()
            downloaded_bytes = 0
            downloaded_count = 0
            
            # Initial print for cleaner output
            sys.stdout.write(f"\rProgress: 0/{num_assets_to_download} (0.00 MB / {total_bytes_to_download / (1024*1024):.2f} MB) [0.00%] Speed: 0.00 MB/s ETA: --s")
            sys.stdout.flush()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_asset = {executor.submit(download_file_with_retries, asset['url'], asset['path'], quiet=True): asset for asset in assets_to_download}
                
                for future in as_completed(future_to_asset):
                    asset = future_to_asset[future]
                    try:
                        success = future.result()
                        if success:
                            downloaded_bytes += asset['size']
                        else:
                            sys.stderr.write(f"\n  Failed to download asset: {asset['url']}\n")

                        downloaded_count += 1
                        
                        elapsed_time = time.time() - start_time
                        if elapsed_time == 0: elapsed_time = 0.001 # Avoid ZeroDivisionError
                        
                        speed = downloaded_bytes / elapsed_time
                        remaining_bytes = total_bytes_to_download - downloaded_bytes
                        
                        eta = remaining_bytes / speed if speed > 0 else float('inf')
                        eta_str = f"{eta:.0f}s" if eta != float('inf') else "--s"

                        progress_percent = (downloaded_bytes / total_bytes_to_download) * 100 if total_bytes_to_download > 0 else 0
                        
                        sys.stdout.write(
                            f"\rProgress: {downloaded_count}/{num_assets_to_download} ({downloaded_bytes / (1024*1024):.2f} MB / {total_bytes_to_download / (1024*1024):.2f} MB) "
                            f"[{progress_percent:.2f}%] Speed: {speed / (1024*1024):.2f} MB/s ETA: {eta_str}"
                        )
                        sys.stdout.flush()
                    except Exception as exc:
                        sys.stderr.write(f"\n  Asset {asset['path']} generated an exception: {exc}\n")
            
            sys.stdout.write("\n") # Newline after progress bar
            print("Asset processing complete.")

    # 5. Generate Configuration Script
    
    # Scripts are now generated directly in the root, not in .flashcraft/configs
    # and named run_{version}_{config_name}.sh
    launcher_script_name = f"run_{version_id}"
    if use_fabric:
        launcher_script_name += "_fabric"
    if config_name:
        launcher_script_name += f"_{config_name}"
    launcher_script_name += ".sh"

    print(f"Generating launcher script: {launcher_script_name}...")
    cwd = os.getcwd()
    classpath = ":".join([os.path.relpath(p, cwd) for p in cp_parts])
    
    env = ""
    if is_arm:
        env = "export MESA_GL_VERSION_OVERRIDE=4.5\nexport MESA_GLSL_VERSION_OVERRIDE=450\nexport vblank_mode=0"

    # Create mods directory if it doesn't exist (for Fabric)
    if use_fabric:
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
    
    with open(launcher_script_name, "w") as f:
        f.write("#!/bin/bash\n" + env + "\n")
        f.write(" \\\n    ".join(cmd) + "\n")
    
    os.chmod(launcher_script_name, 0o755)

    print(f"\n✨ FlashCraft Setup Complete! {'(Fabric enabled)' if use_fabric else ''}")
    if use_fabric:
        print(f"📁 Put your mods into the 'mods' folder.")
    print(f"👉 To start Minecraft, run: ./{launcher_script_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FlashCraft: Minecraft ARM64/Fabric Setup Tool")
    parser.add_argument("--version", default="1.21")
    parser.add_argument("--user", default="sktryo")
    parser.add_argument("--ram", default="2G")
    parser.add_argument("--fabric", action="store_true", help="Enable Fabric Loader")
    parser.add_argument("--skip-assets", action="store_true")
    parser.add_argument("--config-name", help="Custom name for the configuration (e.g., 'cheats', 'sodium')")
    parser.add_argument("--workers", type=int, default=DEFAULT_MAX_DOWNLOAD_WORKERS,
                        help=f"Number of parallel download threads for assets (default: {DEFAULT_MAX_DOWNLOAD_WORKERS})")
    args = parser.parse_args()
    
    # Set default config_name based on --fabric flag
    if args.config_name is None:
        if args.fabric:
            args.config_name = "fabric"
        else:
            args.config_name = "vanilla"

    setup_minecraft(args.version, args.user, args.ram, args.skip_assets, args.fabric, args.config_name, args.workers)
