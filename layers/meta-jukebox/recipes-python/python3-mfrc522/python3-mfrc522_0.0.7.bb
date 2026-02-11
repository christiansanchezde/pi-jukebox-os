SUMMARY = "A small library for the MFRC522 RFID module"
HOMEPAGE = "https://github.com/pimylifeup/MFRC522-python"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://PKG-INFO;md5=7cf24c2f81e97ab5bf8b934e651a50e9"

# This tells Yocto to download from PyPi
# Automatically figures out the download URL based on the filename
inherit pypi setuptools3

# The checksums ensure we downloaded the right file (Security)
SRC_URI[sha256sum] = "74c7020a4fc4870f5d7022542c36143fba771055a2fae2e5929e6a1159d2bf00"

# Runtime dependencies (What this library needs to run on the board)
RDEPENDS:${PN} += "\
    python3-spidev \
    python3-core \
    rpi-gpio \
"