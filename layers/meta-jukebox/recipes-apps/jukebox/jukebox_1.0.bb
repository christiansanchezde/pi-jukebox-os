SUMMARY = "Professional RFID Jukebox Application"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

# Dependencies
DEPENDS = "python3"
RDEPENDS:${PN} = " \
    python3-core \
    python3-asyncio \
    python3-logging \
    python3-subprocess \
    python3-rpi-gpio \
    python3-spidev \
    python3-mfrc522 \
    bash \
    vlc \
"

inherit systemd useradd

# Create a dedicated system user for the jukebox
USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "-u 1000 -d /usr/share/jukebox -m -s /bin/bash jukebox"

SRC_URI = " \
    file://jukebox.py \
    file://shutdown_button.py \
    file://jukebox_start.sh \
    file://mappings.cfg \
    file://jukebox.service \
    file://shutdown-button.service \
"

S = "${WORKDIR}"

SYSTEMD_PACKAGES = "${PN}"
SYSTEMD_SERVICE:${PN} = "jukebox.service shutdown-button.service"

do_install() {
    # Install application scripts
    install -d ${D}/usr/share/jukebox
    install -m 0755 ${S}/jukebox.py ${D}/usr/share/jukebox/
    install -m 0755 ${S}/shutdown_button.py ${D}/usr/share/jukebox/
    install -m 0644 ${S}/mappings.cfg ${D}/usr/share/jukebox/
    
    # Handle the shell script and the requested USER variable
    install -m 0755 ${S}/jukebox_start.sh ${D}/usr/share/jukebox/
    sed -i 's|/home/USER/jukebox|/usr/share/jukebox|g' ${D}/usr/share/jukebox/jukebox_start.sh

    # Install Systemd Services
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/jukebox.service ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/shutdown-button.service ${D}${systemd_system_unitdir}

    # Ensure logs directory exists and is writeable by the jukebox user
    install -d ${D}/var/log/jukebox
    chown -R jukebox:jukebox ${D}/var/log/jukebox
    chown -R jukebox:jukebox ${D}/usr/share/jukebox
}

FILES:${PN} += " \
    /usr/share/jukebox \
    /var/log/jukebox \
    ${systemd_system_unitdir} \
"