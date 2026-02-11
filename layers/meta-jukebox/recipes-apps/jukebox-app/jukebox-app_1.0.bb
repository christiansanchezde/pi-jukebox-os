SUMMARY = "Main Jukebox Application and Logic"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://jukebox.py \
    file://shutdown_button.py \
    file://mappings.cfg \
    file://jukebox.service \
    file://shutdown-button.service \
"

inherit systemd

SYSTEMD_SERVICE:${PN} = "jukebox.service shutdown-button.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_install() {
    # 1. Install the Python Scripts to /usr/bin
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/jukebox.py ${D}${bindir}/
    install -m 0755 ${WORKDIR}/shutdown_button.py ${D}${bindir}/
    
    # 2. Install the Config file to /usr/bin (or /etc/jukebox if you prefer)
    install -m 0644 ${WORKDIR}/mappings.cfg ${D}${bindir}/

    # 3. Install Systemd Services
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/jukebox.service ${D}${systemd_unitdir}/system/
    install -m 0644 ${WORKDIR}/shutdown-button.service ${D}${systemd_unitdir}/system/
}

FILES:${PN} += "${bindir}/* ${systemd_unitdir}/system/*"