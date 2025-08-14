from typing import Tuple, Any, Union

import numpy as np
import cv2
from scipy import ndimage


def imrescale(img, in_range=(0, 1)):
    eps = 1e-14
    img = img - np.min(img) + in_range[0]
    rescale_img = img / (np.max(img)+eps) * in_range[1]
    return rescale_img


def imnorm(img, norm_value):
    img_norm = img * (norm_value / np.sum(img))
    return img_norm


def is_monotonic(arr):
    """whether the arr input is monotonous"""
    return all(arr[i] <= arr[i+1] for i in range(len(arr)-1)) or all(arr[i] >= arr[i+1] for i in range(len(arr)-1))


def mag2ps(mag, imsize, default_ps=0.3434, default_mag=5.5E6, default_imsize=512):
    """
    根据放大倍数和图像大小，获得 pixel size
    :param mag: 放大倍数
    :param imsize: 图像大小，按像素，如 512x512
    :param default_ps: default_mag 下，default_imsizexdefault_imsize 的图像的放大倍数 (units: Angstrom)
    :param default_mag: 矫正时的标准放大倍数
    :param default_imsize: 矫正时，图像的 pixel 大小
    :return: pixel_size: dict，含键 'height' 和 'width' (units: Angstrom)
    """
    pixel_size = dict()
    pixel_size['height'] = (default_mag / mag) * (default_imsize / imsize[0]) * default_ps
    pixel_size['width'] = (default_mag / mag) * (default_imsize / imsize[1]) * default_ps
    return pixel_size


def get_definition(i_raw: np.ndarray, **kwargs) -> Tuple[Union[Union[float, int], Any], Union[int, Any]]:
    if "method" in kwargs:
        eval_method = kwargs["method"]
    else:
        eval_method = "VGR"

    # 统一为连续的 float32，避免 OpenCV 对 int32 等类型的不支持导致报错
    img = np.asarray(i_raw)
    if img.ndim >= 3 and img.shape[-1] in (3, 4):
        # 若意外为多通道，转灰度
        try:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        except Exception:
            # 退化为取单通道
            img = img[..., 0]
    if img.dtype not in (np.float32, np.float64):
        img = img.astype(np.float32, copy=False)
    img = np.ascontiguousarray(img)

    definition = None
    if eval_method == "Variance":
        definition = float(np.var(img))
        result = []
    elif eval_method == "Laplacian":
        result = cv2.Laplacian(img, cv2.CV_64F)
        definition = float(np.sum(np.abs(result.flat)))
    elif eval_method == "Tenengrad" or eval_method == "VGR":
        sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=5)
        sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=5)
        tenengrad = np.abs(sobelx) + np.abs(sobely)
        definition = float(np.var(tenengrad))
        result = tenengrad

    elif eval_method == "Old-Tenengrad" or eval_method == "TGR":
        sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=5)
        sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=5)
        tenengrad = np.abs(sobelx) + np.abs(sobely)
        definition = float(np.sum(tenengrad))
        result = tenengrad

    elif eval_method == "GaussianDerivative" or eval_method == "GDR":
        gdr_result_x = ndimage.gaussian_filter1d(img, sigma=1, order=1, mode='wrap')
        gdr_result_y = ndimage.gaussian_filter1d(img.T, sigma=1, order=1, mode='wrap')
        gdr_result = gdr_result_x ** 2 + gdr_result_y.T ** 2
        result = gdr_result
        definition = float(np.sum(np.abs(gdr_result)))

    else:
        raise ValueError("Illegal EvalMethod" + eval_method)
    return definition, result

