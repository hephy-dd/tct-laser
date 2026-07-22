import os
from datetime import datetime

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules
from pyinstaller_versionfile import create_versionfile

# Select Qt bindings for pyqtgraph
os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"

import tct_laser

version = tct_laser.__version__
filename = f"tct-laser-{version}.exe"
console = False
block_cipher = None
now = datetime.utcnow()

package_root = os.path.join(os.path.dirname(tct_laser.__file__))
package_icon = os.path.join(package_root, "assets", "icons", "tct-laser.ico")

version_info = os.path.join(os.getcwd(), "version_info.txt")

# Create windows version info
create_versionfile(
    output_file=version_info,
    version=f"{version}.0",
    company_name="MBI Marietta Blau Institute for Particle Physics",
    file_description="TCT-Laser control and measurements",
    internal_name="TCT-Laser",
    legal_copyright=f"Copyright © {now.year} MBI. All rights reserved.",
    original_filename=filename,
    product_name="TCT-Laser",
)

matplotlib_backends = [
    "matplotlib.backends.backend_svg",
]

comet_drivers = [
    "comet.driver.hephy.pilascontroller",
    "comet.driver.hephy.corvuscontroller",
    "comet.driver.mbi.tablecontrol",
    "comet.driver.itk.corvustt",
    "comet.driver.nkt_photonics.pilas",
    "comet.driver.rohde_schwarz.rto6",
    "comet.driver.rohde_schwarz.rtp164",
    "comet.driver.thorlabs.pm100",
]

binaries = []
binaries.extend(collect_dynamic_libs("libusb_package"))

hiddenimports = []
hiddenimports.extend(matplotlib_backends)
hiddenimports.extend(comet_drivers)
hiddenimports.extend(collect_submodules("pyvisa"))
hiddenimports.extend(collect_submodules("pyvisa_py"))
hiddenimports.extend(collect_submodules("serial"))
hiddenimports.extend(collect_submodules("usb"))
hiddenimports.extend(collect_submodules("libusb_package"))
hiddenimports.extend(collect_submodules("gpib_ctypes"))

a = Analysis(
    ["entry_point.py"],
    pathex=[os.getcwd()],
    binaries=binaries,
    datas=[
        (os.path.join(package_root, "assets", "icons", "*.ico"), os.path.join("tct_laser", "assets", "icons")),
        (os.path.join(package_root, "assets", "icons", "*.svg"), os.path.join("tct_laser", "assets", "icons")),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=filename,
    version=version_info,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console,
    icon=package_icon,
)
