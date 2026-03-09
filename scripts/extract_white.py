# Read in library clusters from SLUG
"""
Paths: use COMP_MAIN_DIR, COMP_PSF_PATH, COMP_BAO_PATH env vars, or --directory.
When unset, default to project root (repo root, parent of scripts/).
"""
import argparse
import glob
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import astropy.io.fits as pyfits
import astropy.units as u
import numpy as np
from astropy.io import fits

# Repo root (scripts/extract_white.py -> parent.parent)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _path_from_env(env_key: str, default: Path) -> Path:
    raw = os.environ.get(env_key)
    if raw:
        return Path(raw).resolve()
    return (PROJECT_ROOT / default).resolve() if not default.is_absolute() else default.resolve()


parser = argparse.ArgumentParser(description="Process galaxies in batches.")
parser.add_argument(
    "-ncl", "--ncl", type=int, default=500, help="number of star clusters"
)
parser.add_argument(
    "-eradius",
    "--eradius",
    type=int,
    default=None,
    help="effective radius of star clusters",
)
parser.add_argument(
    "-galaxy",
    "--galaxy",
    type=str,
    default="ngc628-c",
    help="Mass-radius relation to compute effective radii",
)
parser.add_argument(
    "-dmod",
    "--dmod",
    type=float,
    default=29.98,
    help="distance modulus of target galaxy",
)
parser.add_argument("-outname", "--outname", type=str, default=None, help="Output name")
parser.add_argument(
    "--directory",
    type=str,
    default=None,
    help="Main run directory (default: COMP_MAIN_DIR env or project root)",
)
parser.add_argument(
    "--sciframe",
    type=str,
    default=None,
    help="Path to the white-light science frame FITS file",
)
args = parser.parse_args()

main_dir = args.directory or os.environ.get("COMP_MAIN_DIR", str(PROJECT_ROOT))
main_dir = os.path.abspath(main_dir)
PSFpath = str(_path_from_env("COMP_PSF_PATH", Path("PSF_all")))
baopath = str(_path_from_env("COMP_BAO_PATH", Path("baolab")))

os.chdir(main_dir)
minsep = False
filt = "white"
galn = f"{args.galaxy}_{filt}-R17v100"
gal = args.galaxy.split("_")[0]
gal_dir = os.path.join(main_dir, galn)
galdir = os.path.join(main_dir, galn)
logfile = f"output_{gal}_{filt}.txt"
# check and move the config files for SExtractor
pydir = os.path.join(gal_dir, filt)
# define constants
num_cores = multiprocessing.cpu_count()  # Number of CPU cores available
processes = []
galaxies = np.load("galaxy_names.npy")
gal_filters = np.load("galaxy_filter_dict.npy", allow_pickle=True).item()

# nframe = args.nframe
nsf = True
pixscale_wfc3 = 0.04
pixscale_acs = 0.05
# maglim = array([18, 26], dtype=float)
merr_cut = 0.3  # change to 0.5
binsize = 0.3
nums_perframe = args.ncl
sigma_pc = (
    100  # physical size of Gaussian filter for distributing clusters on sci frame
)
xcol = 0  # specifies which column in the data contains the x-coordinates
ycol = 1  # specifies which column in the data contains the x-coordinates
tolerance = 3  # tolerance in units of px, testing 5 pixels
minsep = False


def phys_to_pix(args):
    acpx, galdist, phys = args
    theta = np.arctan(phys / (galdist * u.pc))
    theta = theta.to(u.arcsec)
    pix_val = theta / (acpx * u.arcsec)
    return pix_val.value


##############Helper functions#############################
def mass_to_radius(args):
    """
    Convert mass to radius using a logarithmic relationship and account for random variation.

    Args:
        args (tuple): A tuple containing:
            - libmass (float or array-like): The input mass values.
            - n_trial (int or None): The number of trials for generating random variations. If None, no variation is applied.
            - model (str): The model to use ('Krumholz19' or 'Ryon17').

    Returns:
        numpy.ndarray: The mean radius values after applying random variation (if applicable).
    """

    libmass, n_trial, model = args
    log_libmass = np.log10(libmass)  # Compute log10(libmass)

    if model == "Krumholz19":
        # Logarithmic conversion and exponentiation
        librad = 10 ** (0.1415 * log_libmass)
        rad_lib = np.log10(librad)

        if n_trial is not None:
            # Generate random variations and calculate the mean radius
            sigma_mr = -0.2103855
            random_variations = np.random.randn(len(rad_lib), n_trial) * sigma_mr
            mean_r = rad_lib[:, None] + random_variations
            mean_r = np.mean(mean_r, axis=1)
        else:
            mean_r = rad_lib  # No random variations applied

    elif model == "Ryon17":
        # Compute librad using the OLS equation
        librad = -7.775 + 1.674 * log_libmass

        # Apply the cap: if log10(libmass) > 5.5, set librad to the capped value
        cap_value = -7.775 + 1.674 * 5.2  # Compute librad at log10(libmass) = 5.5
        librad = np.where(log_libmass > 5.2, cap_value, librad)

        mean_r = 10**librad  # Ensure consistency in return format

    else:
        raise NotImplementedError("Model not implemented, exiting...")

    return mean_r


def clear_directory(directory):
    if os.path.exists(directory):
        try:
            # for filename in os.listdir(directory):
            #     file_path = os.path.join(directory, filename)
            #     if os.path.isfile(file_path) or os.path.islink(file_path):
            #         os.unlink(file_path)
            #     elif os.path.isdir(file_path):
            #         shutil.rmtree(file_path)
            print(f"All files removed from {directory}")
        except Exception as e:
            print(f"Error removing files from {directory}: {e}")
    else:
        os.makedirs(directory)
        print(f"Directory {directory} created")


# Apply the mask to get selected indices
def select_bright(mask, phot_neb_ex):
    idx_select_mass = np.where(mask)[0]
    phot_neb_ex_veg = phot_neb_ex[idx_select_mass]
    phot_bright = phot_neb_ex_veg[:, -2]
    idx_bright = np.where(phot_bright + 29.98 < 22)
    return idx_bright


##############################################################w

# Use NGC 628 as an example
galaxy_names = [args.galaxy]
galaxies = np.load(os.path.join(main_dir, "galaxy_names.npy"))
gal_filters = np.load(
    os.path.join(main_dir, "galaxy_filter_dict.npy"), allow_pickle=True
).item()
allfilters_cam = []

for galaxy_name in galaxy_names:
    galaxy_name = galaxy_name.split("_")[0]
    for filt, cam in zip(gal_filters[galaxy_name][0], gal_filters[galaxy_name][1]):
        filt = filt.upper()
        cam = cam.upper()
        if cam == "WFC3":
            cam = "WFC3_UVIS"
        filt_string = f"{cam}_{filt}"
        allfilters_cam.append(filt_string)
allfilters_cam = list(set(allfilters_cam))

# Galaxy and paths
galaxy = "ngc628-c"
fits_path = main_dir

# Load galaxy names and filters
galaxies = np.load(os.path.join(fits_path, "galaxy_names.npy"))
gal_filters = np.load(
    os.path.join(fits_path, "galaxy_filter_dict.npy"), allow_pickle=True
).item()
filters = gal_filters[galaxy]

# Sort filter names in desired order
filter_names = sorted(filters[0])  # Ensures filters are ordered, e.g., f275, f336, etc.

# Auto-search for FITS files based on sorted filter names
fits_files = {
    filter_name: glob.glob(f"{fits_path}/{galn}/*{filter_name}*.fits")[0]
    for filter_name in filter_names
}

# Read FITS files dynamically based on sorted filters
fits_data = {}
headers = {}
for filter_name in filter_names:
    fits_data[filter_name], headers[filter_name] = fits.getdata(
        fits_files[filter_name], header=True
    )

# Example: Verify the order of fits_data and headers
for filter_name in filter_names:
    print(
        f"Filter: {filter_name}, Data Shape: {fits_data[filter_name].shape}, Header: {headers[filter_name]['NAXIS1']}"
    )

fname_list = [f.lower()[-5:] for f in filter_names]

# nframe = args.nframe
nums_perframe = args.ncl
# reff = args.eradius

start_time = time.time()

cams = gal_filters[args.galaxy]
minsep = False
filt = "white"
galn = f"{args.galaxy}_{filt}-R17v100"
gal = args.galaxy.split("_")[0]
gal_dir = os.path.join(main_dir, galn)
galdir = os.path.join(main_dir, galn)
logfile = f"output_{gal}_{filt}.txt"
# check and move the config files for SExtractor
pydir = os.path.join(gal_dir, filt)
# pipe all fits to .txt file
fits_dir = os.path.join(pydir, "synthetic_fits")
apcorrfile = f"avg_aperture_correction_{gal}.txt"
os.chdir(fits_dir)

# import exposure time
zpfile = os.path.join(gal_dir, f"header_info_{gal}.txt")
filters, instrument, zpoint = np.loadtxt(
    zpfile, unpack=True, skiprows=0, usecols=(0, 1, 2), dtype="str"
)
if args.sciframe is not None:
    sciframepath = os.path.abspath(args.sciframe)
    if not os.path.exists(sciframepath):
        sys.exit(f"Provided --sciframe not found: {sciframepath}")
    print(f"Using provided science frame: {sciframepath}")
elif "5194" in gal:
    pattern = os.path.join(gal_dir, f"hlsp_legus_hst_*{gal}_{filt}_*sci.fits")
    matching_files = glob.glob(pattern)
    if not matching_files:
        sys.exit(f"No matching file for galaxy '{gal}' and filter '{filt}'")
    sciframepath = os.path.abspath(matching_files[0])
    print(f"Found matching file: {sciframepath}")
elif filt == "white":
    candidates = glob.glob(os.path.join(gal_dir, f"*{gal}*white*.fits"))
    if not candidates:
        candidates = glob.glob(os.path.join(gal_dir, "white_dualpop_s2n_white_remake.fits"))
    if not candidates:
        sys.exit(
            f"No white-light science frame found in {gal_dir}. "
            "Use --sciframe to specify the path."
        )
    sciframepath = os.path.abspath(candidates[0])
    print(f"Found matching file: {sciframepath}")
else:
    pattern = os.path.join(gal_dir, f"hlsp_legus_hst_*{gal}_{filt}_*drc.fits")
    matching_files = glob.glob(pattern)
    if not matching_files:
        sys.exit(f"No matching file for galaxy '{gal}' and filter '{filt}'")
    sciframepath = os.path.abspath(matching_files[0])
    print(f"Found matching file: {sciframepath}")
match = np.where(filters == filt)
zp = 1
hd = pyfits.getheader(sciframepath)
if np.size(zp) == 0:
    sys.exit("Wrong instrument/filter names! Check the input file! \nQuitting...")
expt = hd["EXPTIME"]
print("zp: ")
print(zp)
print("expt: ")
print(expt)

# set aperture
# readme_file = os.path.join(gal_dir, f"automatic_catalog_{gal}.readme")
readme_files = glob.glob(os.path.join(gal_dir, f"automatic_catalog*_{gal}.readme"))
readme_file = readme_files[0]


with open(readme_file) as f:
    content = f.read()

# Match aperture radius, distance modulus, and CI using regular expressions
patterns = [
    (
        r"The aperture radius used for photometry is (\d+(\.\d+)?)\.",
        "User-aperture radius",
    ),
    (r"Distance modulus used (\d+\.\d+) mag \((\d+\.\d+) Mpc\)", "Galactic distance"),
    (
        r"This catalogue contains only sources with CI[ ]*>=[ ]*(\d+(\.\d+)?)\.",
        "CI value",
    ),
]

for pattern, label in patterns:
    match = re.search(pattern, content)
    if match:
        if "distance" in label:
            galdist = float(match.group(2)) * 1e6
        elif "CI" in label:
            ci = float(match.group(1))
        else:
            useraperture = float(match.group(1))
    else:
        raise FileNotFoundError(label + " not found in the readme.")
fitsdir = os.path.join(pydir, "synthetic_fits")
os.chdir(fitsdir)
print(fitsdir)
# Construct the correct search patterns
if args.eradius is not None:
    reff_tag = f"reff{args.eradius:.2f}"
    print(f"[INFO] Filtering for frames with {reff_tag} ...")
    frame_pattern = f"{args.galaxy}*_{args.outname}*{reff_tag}*.fits"
    coord_pattern = f"{args.galaxy}*{reff_tag}*_{args.outname}.txt"
else:
    print("[INFO] No --eradius specified; including all reff frames.")
    frame_pattern = f"{args.galaxy}*_{args.outname}_reff*.fits"
    coord_pattern = f"{args.galaxy}*_{args.outname}.txt"

# frames_output = [p for p in glob.glob(frame_pattern) if not any(x in p for x in ["cmppsf", "temp", "validation", "vframe"])]
# coords_output = [
#     p for p in glob.glob(coord_pattern)
#     if not any(x in p for x in ["cmppsf", "temp", "validation", "vframe"])
# ]
frames_output = (
    subprocess.check_output(
        f'ls {frame_pattern} | grep -E -v "cmppsf|temp|validation|vframe"',
        shell=True,
        universal_newlines=True,
    )
    .strip()
    .split("\n")
)

# Coords
coords_output = (
    subprocess.check_output(
        f'ls {coord_pattern} | grep -E -v "cmppsf|temp|validation|vframe"',
        shell=True,
        universal_newlines=True,
    )
    .strip()
    .split("\n")
)
# coords_output = (
#     subprocess.check_output(
#         f'ls {coord_pattern} | grep -E -v "cmppsf|temp|validation|vframe"',
#         shell=True,
#         universal_newlines=True,
#     )
#     .strip()
#     .split("\n")
# )


with open(f"list_frames_{gal}_{filt}_{args.outname}.ls", "a") as frames_file:
    frames_file.write("\n".join(frames_output) + "\n")
with open(f"list_coords_{gal}_{filt}_{args.outname}.ls", "a") as coords_file:
    coords_file.write("\n".join(coords_output) + "\n")

if not os.path.exists(os.path.join(gal_dir, f"r2_wl_aa_{gal}.config")):
    sys.exit(
        f"cannot find the file 'r2_wl_aa_{gal}.config' in the main dir \nquitting now..."
    )
if not os.path.exists(os.path.join(main_dir, "output.param")):
    sys.exit("cannot find the file 'output.param' in the main dir \nquitting now...")
if not os.path.exists(os.path.join(main_dir, "default.nnw")):
    sys.exit("cannot find the file 'default.nnw' in the main dir \nquitting now...")

if not os.path.exists(os.path.join(pydir, "s_extraction")):
    os.makedirs(os.path.join(pydir, "s_extraction"))
# else :
#     os.system('rm '+pydir+'/s_extraction/* ')

# os.system("scp " + gal_dir + f"/r2_wl_aa_{gal}.config " + pydir + "/s_extraction/.")
# os.system("scp " + main_dir + "/output.param " + pydir + "/s_extraction/.")
# os.system("scp " + main_dir + "/default.nnw " + pydir + "/s_extraction/.")


s_extraction_dir = os.path.join(pydir, "s_extraction")
os.makedirs(s_extraction_dir, exist_ok=True)

config_src = os.path.join(gal_dir, f"r2_wl_aa_{gal}.config")
param_src = os.path.join(main_dir, "output.param")
nnw_src = os.path.join(main_dir, "default.nnw")

for src in [config_src, param_src, nnw_src]:
    if not os.path.exists(src):
        raise FileNotFoundError(f"[ERROR] Missing required file: {src}")
    shutil.copy2(src, s_extraction_dir)
    print(f"[INFO] Copied {os.path.basename(src)} → {s_extraction_dir}")
# move to s_extraction directory
path = pydir + "/s_extraction"
os.chdir(path)

source = pydir + f"/synthetic_fits/list_frames_{gal}_{filt}_{args.outname}.ls"
destination = path + f"/list_frames_{gal}_{filt}_{args.outname}.ls"
shutil.copyfile(source, destination)

source = pydir + f"/synthetic_fits/list_coords_{gal}_{filt}_{args.outname}.ls"
destination = path + f"/list_coords_{gal}_{filt}_{args.outname}.ls"
shutil.copyfile(source, destination)

# Filter again by reff if specified
if args.eradius is not None:
    framename = np.loadtxt(
        path + f"/list_frames_{gal}_{filt}_{args.outname}.ls", dtype="str"
    )
    framename = [f for f in framename if f"reff{args.eradius:.2f}" in f]
else:
    framename = np.loadtxt(
        path + f"/list_frames_{gal}_{filt}_{args.outname}.ls", dtype="str"
    )

if np.size(framename) == 1:
    framename = np.append(framename, "string")
    framename = framename[np.where(framename[1] == "string")]

#####   write the file 'catalog_ds9_sextractor.reg'
# replace output catalog to avoid parallelised overwriting
with open(f"r2_wl_aa_{gal}.config") as config_file:
    config = config_file.readlines()

for i, line in enumerate(config):
    if line.startswith("CATALOG_NAME"):
        # Update the line with the new catalog name
        config[i] = f"CATALOG_NAME   r2_wl_dpop_detarea_{gal}_{filt}.cat\n"

# Write the modified content back to the r2.config file if changes were made
with open(f"r2_wl_aa_{gal}.config", "w") as config_file:
    config_file.writelines(config)

for z in range(0, len(framename)):
    framepath = pydir + "/synthetic_fits/" + framename[z]
    print("Executing SExtractor on image : ", framename[z])
    #####   here we run sextractor
    command = "sex " + framepath + f"  -c r2_wl_aa_{gal}.config"
    os.system(command)

    xx, yy, fwhmdeg, source_class, mag_best = np.loadtxt(
        f"r2_wl_dpop_detarea_{gal}_{filt}.cat", unpack=True, skiprows=5, dtype="str"
    )
    outputfile = "cat_ds9_sextr_" + framename[z] + ".reg"
    file = open(outputfile, "w")
    file.write(
        'global color=blue width=5 font="helvetica 15 normal roman" highlite=1 \n'
    )
    file.write("image\n")

    for i in range(len(xx)):
        c2 = str(xx[i])
        c3 = str(yy[i])
        newline = "circle(" + c2 + "," + c3 + ",7) \n"
        file.write(newline)
    file.close()

    # --- -- - - write the sex_*.coo file - after sextraction, before photometry
    outputfile = "sex_" + framename[z] + ".coo"
    file = open(outputfile, "w")
    for i in range(len(xx)):
        c2 = str(xx[i])
        c3 = str(yy[i])
        newline = c2 + " " + c3 + "\n"
        file.write(newline)
    file.close()

print("\n Source extraction is completed! \n")
