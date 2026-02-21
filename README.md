# FlashCraft

A lightweight, Python-based environment builder for running Minecraft Java Edition on **aarch64 Linux** (like Raspberry Pi 4/5, Asahi Linux, etc.).

## ✨ Features
- **Auto-Version Discovery**: Fetches any version manifest directly from Mojang API.
- **ARM64 Optimization**: 
  - Automatically swaps x86_64 LWJGL natives with aarch64 versions from Maven Central.
  - Injects Mesa environment variables for OpenGL version spoofing (required for RPi4).
- **Zero-Dependency**: Uses only standard Python libraries.

## 🛠 Usage
### 1. Basic Setup
Run the setup script with your desired version:
```bash
python3 setup_mc.py --version 1.21 --user MyUsername --ram 4G
```

### 2. Download Assets
(Optional but recommended for full graphics/sound)
```bash
python3 download_assets.py
```

### 3. Launch
```bash
./run.sh
```

## ⚙️ Command Line Options
- `--version`: Specify Minecraft version (default: 1.21)
- `--user`: Set player username
- `--ram`: Set Max RAM allocation (default: 2G)

## ⚠️ Requirements
- **Java 21** (for 1.20.5+) or appropriate JRE for older versions.
- aarch64 Linux distribution.

## Disclaimer
This tool is for educational purposes. It does not contain or distribute any Minecraft binary files. You must provide your own credentials or play in offline/demo mode. Please support Mojang by purchasing the game!