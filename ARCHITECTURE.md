# Jukebox Hardware & Software Architecture

## Hardware Interface
The application runs on a Raspberry Pi 3B using the following Pinout (BCM Numbering):

| Component | Interface | BCM Pin | Physical Pin | Notes |
|-----------|-----------|---------|--------------|-------|
| **RFID**  | SPI0      | -       | 19, 21, 23   | MFRC522 Reader |
| **RFID**  | GPIO      | 25      | 22           | Reset Pin |
| **LED G** | GPIO      | 6       | 31           | Status: Ready |
| **LED B** | GPIO      | 12      | 32           | Status: Active |
| **LED R** | GPIO      | 5       | 29           | Status: Error |
| **Button**| GPIO      | 13      | 33           | Shutdown (Active Low) |

## Software Stack
*   **OS:** Yocto Project (Scarthgap)
*   **Init System:** Systemd
*   **Runtime:** Python 3.12+
*   **Audio Engine:** VLC (cvlc) via subprocess
*   **IPC:** None (Monolithic application)

## Service Management
The system runs two dedicated services:
1.  `jukebox.service`: Main application logic. Auto-restarts on failure.
2.  `shutdown-monitor.service`: Polls the physical button for safe shutdown.

## 🧠 Developer Refresher: How this Yocto Build Works

*This section is a note to self on how the Yocto/Kas machinery operates in this project.*

### 1. The Build Flow (Kas vs. BitBake)
Instead of manually cloning layers and sourcing scripts, we use **Kas**.
*   **Input:** `kas-project.yml`
*   **Process:** Kas parses the YAML $\rightarrow$ Clones repositories (Poky, Meta-RPi) $\rightarrow$ Generates `conf/local.conf` & `conf/bblayers.conf` $\rightarrow$ Runs BitBake.
*   **Command:** `kas build kas-project.yml`

### 2. The Recipe Hierarchy
The build follows a specific chain of command. If you need to add a feature, you must know where to plug it in:

1.  **The Image (`jukebox-image.bb`)**
    *   *Role:* The "Shopping List."
    *   *What it does:* Defines the final `.wic` file. It inherits `core-image` and adds packages via `IMAGE_INSTALL`.
    *   *Edit this if:* You need to add a global tool like `htop`, `vim`, or a new library.

2.  **The Application (`jukebox-app.bb`)**
    *   *Role:* The "Installer."
    *   *What it does:* Takes the local Python files (`SRC_URI`), moves them to the staging directory (`do_install`), and registers the Systemd service.
    *   *Edit this if:* You change the Python script names, add a new config file, or change the service logic.

3.  **The Dependencies (`python3-mfrc522.bb`)**
    *   *Role:* The "Fetcher."
    *   *What it does:* Downloads source code from PyPi, verifies the Checksum, and packages it.
    *   *Edit this if:* You need to upgrade the library version or fix a checksum mismatch.

### 3. Key Yocto Variables Cheat Sheet
When writing recipes, remember these variables:

| Variable | Meaning | Example in this project |
| :--- | :--- | :--- |
| **`${WORKDIR}`** | The sandbox where BitBake unpacks files. | Where `jukebox.py` sits before installation. |
| **`${S}`** | The Source directory (inside Workdir). | Where the `mfrc522` tarball is unpacked. |
| **`${D}`** | The Destination directory. | The "fake" root file system. Files put here end up on the Pi. |
| **`${bindir}`** | The binary directory. | Maps to `/usr/bin`. |
| **`${systemd_unitdir}`** | Systemd location. | Maps to `/lib/systemd`. |

### 4. Common Tasks

**How to add a new Python file:**
1.  Place the file in `recipes-apps/jukebox-app/files/`.
2.  Add it to `SRC_URI` in `jukebox-app.bb`.
3.  Add an `install` command in the `do_install()` function:
    ```bash
    install -m 0755 ${WORKDIR}/my_new_script.py ${D}${bindir}/
    ```

**How to debug a build failure:**
If a task fails, look at the log file path provided in the error message.
*   *Fetch Error:* Check `SRC_URI` and Checksums.
*   *Install Error:* You probably tried to install a file that wasn't in `SRC_URI`, or you typo'd the filename.
*   *Runtime Error:* If the app crashes on the Pi, check `RDEPENDS`. Did you forget to list a Python library required by the script?

## 🧠 Developer Refresher: The Core Concepts

*Future Me: If you haven't touched this project in 6 months, read this first to download the context back into your brain.*

### 1. What actually is "Yocto"?
It is important to remember that **Yocto is not a Linux Distribution** (like Ubuntu or Fedora).
Yocto is a **Factory** for creating custom Linux Distributions.

*   **Ubuntu:** You download a finished binary image. You get what they give you.
*   **Yocto:** You download the *source code* for everything (the Kernel, the Compiler, the Shell, Python, and your App). You press "Go," and Yocto compiles all of it from scratch to create a custom OS image tailored exactly to your hardware.

**Why do we use it?**
Because for an embedded device (like this Jukebox), we don't want the bloat of a desktop OS. We want a tiny, fast, read-only system that does exactly one thing perfectly.

### 2. The Engine: BitBake
If Yocto is the factory, **BitBake** is the robot worker on the assembly line.
BitBake does not know what "Linux" is. It only knows how to follow instructions called **Recipes**.

**The BitBake Workflow:**
When you run `bitbake jukebox-image`, it does the following for *every single package* (thousands of them):
1.  **Fetch:** Go to the internet (Git/HTTP) and get the source code.
2.  **Unpack:** Open the zip/tar file into a working directory.
3.  **Patch:** Apply any custom fixes (like our `config.txt` changes).
4.  **Configure:** Prepare the build (like running `./configure` or `cmake`).
5.  **Compile:** Turn source code into binaries (using the cross-compiler).
6.  **Install:** Copy the binaries to a "fake" destination folder.
7.  **Package:** Wrap those files into an `.rpm` or `.ipk`.

### 3. The Instructions: Recipes & Layers
*   **Recipe (`.bb`):** A single instruction sheet. It tells BitBake: "Here is where you download Python, here is how you compile it, and here is where you put the binary."
*   **Layer (`meta-*`):** A folder containing a collection of recipes.
    *   `poky`: The core layer (contains the compiler, libc, standard tools).
    *   `meta-raspberrypi`: The hardware layer (contains the Kernel and Bootloader for the Pi).
    *   `meta-jukebox`: **Our** layer. This is where our custom logic lives.

**The Golden Rule:** Never edit files inside `poky` or `meta-raspberrypi`. Always create a "bbappend" or a new recipe in `meta-jukebox`. This keeps our code clean and portable.

### 4. The Orchestrator: Kas
**Why did we use Kas?**
Standard Yocto setup is painful. Usually, you have to:
1.  Manually `git clone` 5 different repositories.
2.  Manually switch them all to the matching branch (e.g., `scarthgap`).
3.  Run a setup script (`source oe-init-build-env`).
4.  Manually edit `conf/local.conf` to set the machine type and settings.

If you send your project to a friend, they have to do all that manually, and they might get the wrong version.

**Kas solves this.**
Kas is a wrapper around BitBake. It uses a single YAML file (`kas-project.yml`) to define:
*   Which URL to clone.
*   Which commit hash to use.
*   What configuration variables to set.

**The Benefit:**
You can delete your entire `jukebox-os` folder today, come back in 5 years, run `kas checkout`, and you are guaranteed to get the **exact** same build environment you had today. It turns "Infrastructure" into "Code."