from skimage import morphology
import numpy as np
import cv2
from zhoutomo_client.processing.legacy.utils import imrescale


def bg_conv_gauss_corr(bg_mask: np.ndarray, convd, thresh) -> bool:
    xdim = bg_mask.shape[0]
    ydim = bg_mask.shape[1]

    Y, X = np.meshgrid(np.arange(0, ydim, 1), np.arange(0, xdim, 1))
    A = -1 * ((Y - int(np.ceil((ydim - 1) / 2))) ** 2 + (X - int(np.ceil((xdim - 1) / 2))) ** 2) * np.log(
        2) / convd ** 2
    Kernel = np.exp(A)

    mask_pad = np.zeros((2 * xdim - 1, 2 * ydim - 1))
    mask_pad[int(np.floor((xdim + 1) / 2)) - 1: int(np.floor((xdim + 1) / 2) + xdim - 1),
             int(np.floor((ydim + 1) / 2)) - 1: int(np.floor((ydim + 1) / 2) + ydim - 1)] = bg_mask

    Ker_pad = np.zeros((2 * xdim - 1, 2 * ydim - 1))
    Ker_pad[int(np.floor((xdim + 1) / 2)) - 1: int(np.floor((xdim + 1) / 2) + xdim - 1),
            int(np.floor((ydim + 1) / 2)) - 1: int(np.floor((ydim + 1) / 2) + ydim - 1)] = Kernel

    Conv = np.fft.fftshift(
        np.fft.ifft2(np.fft.fft2(np.fft.ifftshift(mask_pad)) * np.fft.fft2(np.fft.ifftshift(Ker_pad))))
    after_conv = Conv[int(np.floor((xdim + 1) / 2)) - 1:int(np.floor((xdim + 1) / 2) + xdim - 1),
                      int(np.floor((ydim + 1) / 2)) - 1: int(np.floor((ydim + 1) / 2) + ydim - 1)]
    after_conv = after_conv > thresh
    return after_conv


def create_loose_mask(data2: np.ndarray, **kwargs) -> np.ndarray:
    """
    This function produce 2D mask especially for bm3d.
    :param data2: 2D image
    :param kwargs: MinSize=3000, determine the area of small regions out of the target. DiskSize=25, determine the
    thickness of boundary
    :return:
    mask
    """

    if "MinSize" in kwargs:
        min_size = kwargs["MinSize"]
    else:
        min_size = 3000
    if "DiskSize" in kwargs:
        disk_size = kwargs["DiskSize"]
    else:
        disk_size = 25

    # This edge preserve smoothing method should be considered again.
    img_U8 = imrescale(data2, (0, 255)).astype(np.uint8)
    img_blurred = cv2.GaussianBlur(img_U8, (5, 5), 0)
    ret3, th3 = cv2.threshold(img_blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    img_cleaned = morphology.remove_small_objects(th3, min_size=min_size, connectivity=2)
    se = morphology.disk(disk_size)
    img_dilated = cv2.dilate(img_cleaned, se)
    mask = np.array(bg_conv_gauss_corr(img_dilated, 3, 0.1)) == False
    return mask
