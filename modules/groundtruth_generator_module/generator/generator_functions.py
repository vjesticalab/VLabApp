import os
import numpy as np
import cv2
"""from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
import tifffile
import nd2
from PyQt5.QtWidgets import QMessageBox

def mask_plates(image):
    # sam_checkpoint to download form git and put in a useful folder, then copy the path here
    sam_checkpoint = "support_files/SAM/sam_vit_h_4b8939.pth"
    model_type = "vit_h"
    device = "cpu"
    sam = sam_model_registry[model_type](checkpoint=sam_checkpoint)
    sam.to(device=device)
    mask_generator = SamAutomaticMaskGenerator(sam)
    masks = mask_generator.generate(image)
    return masks


def gt_generator(image_path, result_path):
   if image_path.endswith('.nd2'):
       image = nd2.imread(image_path)
   elif image_path.endswith('.tiff'):
       image = tifffile.imread(image_path)
   
   for time_point in range(image.shape[0]):
      image_t = image[time_point,0,:,:]
      info = np.iinfo(image_t.dtype) # Get the information of the incoming image type
      image_norm = image_t.astype(np.float64) / info.max # Normalize the data to 0 - 1
      image_norm = 255 * image_norm # And scale by 255
      image_rgb = cv2.cvtColor(image_norm.astype(np.uint8), cv2.COLOR_BGR2RGB)

      # Calcultate the mask with SAM network
      masks = mask_plates(image_rgb)

      image_mask = np.zeros((image_norm.shape[0], image_norm.shape[1]))
      i = 0
      for ann in masks:
         i += 1
         data = ann['segmentation']
         image_mask[(data == True) & (image_mask == 0)] = i # if binary mask : image_mask[data == True] = 1
      
      image_name = os.path.basename(image_path).split('.')[0]+'_t'+str(time_point)
      tifffile.imwrite(result_path+'/'+image_name+'.tif', image_mask)
"""
def gt_generator(image_path, result_path):
    pass


def main(path, kind):
   
   if kind == 'singleFile':
      # Create the result's folder if it doesn't already exist
      image_path = path
      folder_path = os.path.dirname(path)
      result_path = folder_path + "/masks_for_groundtruth/"
      if not os.path.exists(result_path):
            os.makedirs(result_path)

      gt_generator(image_path, result_path)
            
   elif kind == 'singleFolder':
      # Create the result's folder if it doesn't already exist
      result_path = path + "/masks_for_groundtruth/"
      if not os.path.exists(result_path):
            os.makedirs(result_path)
      
      # List the images to analyse into the folder - accepted format : .nd2 and .tif
      images = sorted([i for i in os.listdir(path) if (i.endswith('.nd2') or i.endswith('.tif'))])

      for image_name in images:
         gt_generator(path+'/'+image_name, result_path)
