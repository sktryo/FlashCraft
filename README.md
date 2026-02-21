# FlashCraft v1.9.3

A powerful, Python-based environment builder for running Minecraft Java Edition on **aarch64 Linux** (like Raspberry Pi 4/5, Asahi Linux, etc.). Fully supports Fabric Loader for enhanced gameplay.

## ✨ Features
- **Auto-Version Discovery**: Fetches any Minecraft version manifest directly from Mojang API.
- **ARM64 Optimization**: 
  - Automatically swaps x86_64 LWJGL natives with aarch64 versions from Maven Central.
  - Injects Mesa environment variables for OpenGL version spoofing (required for RPi4).
- **Fabric Loader Support**: Integrates Fabric Loader for modding and optimization.
- **Robust Asset Downloads**: 
  - **Parallel Downloads**: Utilizes multiple threads (`--workers`) for faster asset acquisition.
  - **Retry Mechanism**: Automatically retries failed downloads with exponential backoff.
  - **User-Agent Spoofing**: Mimics browser requests to prevent server-side blocking.
  - **Timeout Handling**: Prevents indefinite hanging on slow or unresponsive connections.
  - **Detailed Progress Bar**: Shows real-time speed, ETA, and downloaded percentage (pv-like).
- **Zero-Dependency**: Uses only standard Python libraries (except for optional `requests` for robust downloads).

## 🛠 Usage

### 1. (Optional) Install `requests` for robust downloads
For more reliable and robust downloads, especially on unstable networks or with remote servers, it's highly recommended to install the `requests` library:
```bash
pip install requests
# or
pip3 install requests
```

### 2. Setup Minecraft Environment
Run the setup script with your desired Minecraft version and options. This will download all necessary game JARs, libraries, and assets, and generate a launcher script.

#### Example: Vanilla Minecraft 1.21
```bash
python3 setup_mc.py --version 1.21 --user MyVanillaPlayer --ram 2G
# Then launch:
./run_1.21_vanilla.sh
```

#### Example: Fabric-enabled Minecraft 1.21 (for Mods & Cheats)
```bash
python3 setup_mc.py --version 1.21 --fabric --user Notch --ram 4G --config-name cheats --workers 16
# Then launch:
./run_1.21_fabric_cheats.sh
```
*Note: Make sure to place your Fabric mods (e.g., Sodium, Meteor Client) into the auto-created `mods/` folder.*

### ⚙️ Command Line Options
- `--version`: Specify Minecraft version (default: 1.21)
- `--user`: Set player username (default: sktryo)
- `--ram`: Set Max RAM allocation (e.g., `2G`, `4G`) (default: 2G)
- `--fabric`: Enable Fabric Loader integration.
- `--skip-assets`: Skip downloading game assets (useful if you already have them).
- `--config-name`: Custom name for the generated launcher script suffix (e.g., `cheats`, `sodium`). Default is `fabric` if `--fabric` is used, otherwise `vanilla`.
- `--workers`: Number of parallel download threads for assets (default: 8). Adjust for optimal speed on your network.

## ⚠️ Requirements
- **Java 21** (for Minecraft 1.20.5+) or appropriate JRE for older versions.
- aarch64 Linux distribution (e.g., Raspberry Pi OS on RPi4/5).

## Disclaimer
This tool is for educational purposes. It does not contain or distribute any Minecraft binary files. All files are downloaded directly from Mojang and FabricMC servers. You must provide your own credentials or play in offline/demo mode. Please support Mojang by purchasing the game!
