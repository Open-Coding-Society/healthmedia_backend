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
 
def predict_likes_from_image(image_path):
    brightness, saturation, size = extract_image_features(image_path)
 
    X_new = np.array([[brightness, saturation, size]])
 
    y_pred = model.predict(X_new)
 
    print(f"Image: {image_path}")
    print(f"Extracted features - Brightness: {brightness:.2f}, Saturation: {saturation:.2f}, Size: {size:.2f}")
    print(f"Predicted likes: {y_pred[0]:.2f}")
 
    return y_pred[0]
 
data = pd.read_csv('datasets/legoland.csv')
 
X = data[['Brightness', 'Saturation', 'Size']].values
y = data['numLikes'].values
 
model = LinearRegression()
model.fit(X, y)
 
print("Coefficients:", model.coef_)
print("Intercept:", model.intercept_)
 
# Uncomment the following lines to test the image prediction function
# image_path = "path/to/your/image.jpg"
# print(f"Automatic prediction for image {image_path}: {predict_likes_from_image(image_path)}")
 
X_new = np.array([[5.0, 3.0, 4.0]])
y_pred = model.predict(X_new)
print(f"Manual prediction for input {X_new[0]}:", y_pred)