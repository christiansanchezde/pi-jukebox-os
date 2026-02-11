# Force removal of taglib support
PACKAGECONFIG:remove = "taglib"

# Also remove the build dependency to be safe
DEPENDS:remove = "taglib"

# Print a message so we know this file was read (visible in bitbake -e)
python () {
    bb.plain("META-JUKEBOX: Disabling taglib in VLC")
}