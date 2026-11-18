package io.github.iamwilmar.xenoblade3port;

// What identifies this game in the user's files: the rest of the start screen is the same in every port.
// Lo que distingue a este juego en los archivos del usuario: el resto de la pantalla de inicio es igual en cada port.
final class Game {
    static final String NAME = "Xenoblade Chronicles 3";
    static final long APP_ID = 0x010074F013262000L;
    // Versions are recognised by the build ID of the ExeFS main (bytes 0x40-0x53 of the NSO header). KNOWN_BUILDS:
    // {build ID, version, size of VERSION_FILE in that version's RomFS or null}. STRICT_VERSION: only those builds
    // (ports with address-specific patches); otherwise any build of the game is accepted with a notice.
    static final String VERSION = "2.2.0";
    static final String BUILD_ID = "82d187fe9ef9be921b8e1b1cddf7bd287cdb22c1";
    static final String[][] KNOWN_BUILDS = {{"82d187fe9ef9be921b8e1b1cddf7bd287cdb22c1", "2.2.0", "3896736"}};
    static final boolean STRICT_VERSION = false;
    static final String VERSION_FILE = "bf3.arh";  // relative to the RomFS root (null: not checked)
    static final String ROMFS_MARKER = "bf3.ard";  // relative to the RomFS root
    static final String UPDATE_MARKER = null;  // only present with the update applied (null: not checked)
    static final String DLC_MARKER = "bf3_dlc0?.arh";  // in the root of each DLC RomFS; ? and * allowed (null: no DLC)
    // Files the ExeFS folder must contain besides main and main.npdm (the game's own libraries, loaded as they are).
    static final String[] EXEFS_EXTRA = null;

    private Game() {}
}
