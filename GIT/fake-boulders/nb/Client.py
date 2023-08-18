import sys
import math
import random
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
import shapely
import rasterio as rio
import albumentations as A
import albumentations.augmentations.functional as F
import cv2
import os
from pathlib import Path
from colorama import Fore

parameters = sys.argv
#Establishing the Home directory
parent_directory = str(Path(os.getcwd()).parent.parent.parent)
sys.path.append(parent_directory + "/GIT")  
if parameters[2] == 'home':
    output_directory = parent_directory + "/outputs"
else:
    output_directory = parameters[0]

from fbapi import CDBSC, generate_target_noise, generate_fake_boulders, perlin, apply_blur_transformation
from MLtools import create_annotations_mask
from rastertools import raster

# grab all of the options for target raster
all_empty_tifs = []
all_empty_patches = os.listdir(parent_directory + "/fakeboulders/patches-no-boulders/images/")
for image in all_empty_patches:
    if '.tif' in image:
        all_empty_tifs.append(image)
        
gdf_boulders = gpd.read_file(parent_directory  + "GeoDataFrame")

sample_size = int(parameters[1])
for x in range(0, sample_size):
    
    ############## Set Parameters #################
    
    # Feature Parameters
    if parameters[3] == 'random':
        AOI = random.uniform(20, 75)
    else:
        AOI = float(parameters[3])
    if parameters[4] == 'random':
        rim_distance = random.uniform(0.2, 8.0)
    else:
        rim_distance = float(parameters[4])
    fancy_shadows = False
    
    # Raster parameters
    rp = Path(parent_directory + "/fakeboulders/patches-no-boulders/images/", all_empty_tifs[random.randint(0, len(all_empty_tifs) - 1)])
    arr = raster.read_raster(rp, as_image=False)
    meta = raster.get_raster_profile(rp)    
    new_array = arr[random.randint(0, len(arr) - 1)]    
    is_mare = bool(parameters[5])
    AOI_scalar = AOI / 1.2
      
    ###############################################
    print(f"Generating an image with AOI = {AOI}, Rim Distance (in crater radii) = {rim_distance}, and total desntiy = {CDBSC(rim_distance)}")

    # Configure the image metadata to include params
    meta['is_mare'] = is_mare
    meta['AOI'] = AOI
    meta['total_density'] = CDBSC(rim_distance)
    meta['rim_distance'] = rim_distance
    print("Meta configured successfully")

    # Apply noise to target raster
    target_raster_noisey = generate_target_noise(rim_distance = rim_distance, target = new_array, is_mare = is_mare)
    final = output_directory + "/Raster_masks/" + str(x) + ".tif"
    raster.save_raster(Path(final), np.expand_dims(target_raster_noisey, axis=0), profile=meta, is_image=False)
    
    # Generate Boulders
    area_covered, fake_masks, fake_boulders_array, shadow_mask, shadowed_boulder_mask = generate_fake_boulders(rim_distance = rim_distance, AOI = AOI, fancy_shadows = False, gdf_boulders = gdf_boulders, target_raster_noisey = target_raster_noisey)            
    final = output_directory + "/Shadow_masks/" + str(x) + ".tif"
    raster.save_raster(Path(final), np.expand_dims(shadow_mask, axis=0), profile=meta, is_image=False)
    final = output_directory + "/Boulder_masks/" + str(x) + ".tif"
    raster.save_raster(Path(final), np.expand_dims(fake_boulders_array, axis=0), profile=meta, is_image=False)
    
     # Adding boulders to the target raster
    idx_mask_to_add = np.where(fake_boulders_array > 0)
    target_raster_noisey[idx_mask_to_add] = fake_boulders_array[idx_mask_to_add]
     
    # dimmin the final output for AOI
    for i in range(500):
        for j in range(500):
            target_raster_noisey[i][j] -= AOI_scalar
            if target_raster_noisey[i][j] < 0:
                target_raster_noisey[i][j] = 0
    
    # adding shadows to the target raster
    idx_mask_to_add_shadows = np.where(shadow_mask != 0)
    target_raster_noisey[idx_mask_to_add_shadows] = shadow_mask[idx_mask_to_add_shadows]
   
    # Adding shadow-boulder overlap
    target_raster_noisey[np.where(shadowed_boulder_mask > 0)] = shadowed_boulder_mask[np.where(shadowed_boulder_mask > 0)]
    for i in range(500):
        for j in range(500):
            if target_raster_noisey[i][j] < 0:
                target_raster_noisey[i][j] = 0

    print(f"Created image {x + 1} of {sample_size}")
    final = output_directory + "/Final_images/" + str(x) + ".tif"
    raster.save_raster(Path(final), np.expand_dims(apply_blur_transformation(target_raster_noisey), axis=0), profile=meta, is_image=False)