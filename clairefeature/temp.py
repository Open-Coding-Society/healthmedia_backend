from sklearn.linear_model import LinearRegression
import numpy as np
import pandas as pd
from PIL import Image, ImageStat
import os

def extract_image_features(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
 
    img = Image.open(image_path)
 
    if img.mode != 'RGB':
        img = img.convert('RGB')
 
    stat = ImageStat.Stat(img)
    brightness = sum(stat.mean) / len(stat.mean)
 
    r, g, b = stat.mean
    max_rgb = max(r, g, b)
    min_rgb = min(r, g, b)
    saturation = (max_rgb - min_rgb) / max_rgb if max_rgb > 0 else 0
 
    width, height = img.size
    size = (width * height) / 1000000
 
    return brightness, saturation, size

brightness, saturation, size = extract_image_features('model/images/img100.jpg')

print(f"Extracted features - Brightness: {brightness:.2f}, Saturation: {saturation:.2f}, Size: {size:.2f}")