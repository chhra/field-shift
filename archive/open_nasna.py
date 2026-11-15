from pyhdf.SD import SD, SDC
import numpy as np

hdf_path = r"data\raw\modis_sample\MOD13Q1.A2025049.h18v03.061.2025070114722.hdf"

print("Opening MODIS HDF4 file...")
file = SD(hdf_path, SDC.READ)

target_dataset_name = "250m 16 days NDVI"

print(f"Extracting data for: {target_dataset_name}")
sds = file.select(target_dataset_name)

# Read the numerical array data
data = sds.get()
print(f"Data shape: {data.shape}")
print(f"Data type: {data.dtype}")
print(f"Raw minimum value: {np.min(data)}, maximum value: {np.max(data)}")

# Note: MODIS NDVI values typically have a scale factor of 0.0001
# Let's apply it to get actual decimal NDVI values (ignoring fill values for a basic check)
valid_data = data[data != -3000]  # -3000 is often a fill/background value in MODIS
if valid_data.size > 0:
    scaled_ndvi = valid_data * 0.0001
    print(f"Scaled NDVI range: min = {np.min(scaled_ndvi):.4f}, max = {np.max(scaled_ndvi):.4f}")

# Clean up handles
sds.endaccess()
file.end()
print("Done!")





import matplotlib.pyplot as plt
import numpy as np
from pyhdf.SD import SD, SDC

hdf_path = r"data\raw\modis_sample\MOD13Q1.A2025049.h18v03.061.2025070114722.hdf"
file = SD(hdf_path, SDC.READ)
sds = file.select("250m 16 days NDVI")
data = sds.get().astype(float)

# Mask fill values (-3000) so they don't mess up the color scale
data[data == -3000] = np.nan
scaled_ndvi = data * 0.0001

# Plot the image
plt.figure(figsize=(8, 8))
plt.imshow(scaled_ndvi, cmap="YlGn", vmin=0, vmax=1)  # 'YlGn' is Yellow-Green (great for vegetation)
plt.colorbar(label="NDVI")
plt.title("MODIS NDVI - Peartree Farm Region")

# Save the figure as an image file you can click and open
plt.savefig("ndvi_map.png", dpi=300, bbox_inches="tight")
print("Saved NDVI map as ndv_map.png!")

sds.endaccess()
file.end()