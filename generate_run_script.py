
import json
import os

def main():
    with open("client.json", "r") as f:
        data = json.load(f)

    cp_parts = ["client.jar"]
    lib_base = "libraries"
    
    for lib in data["libraries"]:
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

        if "downloads" in lib and "artifact" in lib["downloads"]:
            path = os.path.join(lib_base, lib["downloads"]["artifact"]["path"])
            if "org.lwjgl" in lib["name"] and "natives-linux" in lib["name"]:
                arm64_path = path.replace("natives-linux.jar", "natives-linux-arm64.jar")
                if os.path.exists(arm64_path):
                    path = arm64_path
            cp_parts.append(path)

    classpath = ":".join(cp_parts)

    # RPi4向けの環境変数とJVM引数
    # MESA_GL_VERSION_OVERRIDE で 4.5 を偽装します
    # MESA_GLSL_VERSION_OVERRIDE でシェーダーバージョン 450 を偽装します
    run_script = f"""#!/bin/bash
export MESA_GL_VERSION_OVERRIDE=4.5
export MESA_GLSL_VERSION_OVERRIDE=450
export vblank_mode=0

java -Xmx2G -Xms2G \\
    -Djava.library.path=. \\
    -Dlwjgl.util.NoChecks=true \\
    -cp "{classpath}" \\
    net.minecraft.client.main.Main \\
    --username sktryo \\
    --version 1.21 \\
    --gameDir . \\
    --assetsDir assets \\
    --assetIndex 17 \\
    --uuid 00000000-0000-0000-0000-000000000000 \\
    --accessToken 0 \\
    --userType mojang \\
    --versionType release
"""
    
    with open("run.sh", "w") as f:
        f.write(run_script)
    
    os.chmod("run.sh", 0o755)
    print("RPi4 optimized run.sh generated.")

if __name__ == "__main__":
    main()
