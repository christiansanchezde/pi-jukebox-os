SUMMARY = "A professional Jukebox OS for Raspberry Pi"
LICENSE = "MIT"

# Start with a standard minimal image
inherit core-image

# 1. System Features
IMAGE_FEATURES += "ssh-server-openssh"

# 2. Software to Install
IMAGE_INSTALL += "\
    packagegroup-core-boot \
    kernel-modules \
    \
    python3 \
    python3-pip \
    python3-asyncio \
    python3-mfrc522 \
    vlc \
    \
    jukebox-app \
"

# 3. Set fixed space for the rootfs (optional, but good for SD cards)
IMAGE_ROOTFS_SIZE ?= "819200"