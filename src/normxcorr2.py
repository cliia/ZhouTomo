########################################################################################
# Author: Ujash Joshi, University of Toronto, 2017                                     #
# Based on Octave implementation by: Benjamin Eltzner, 2014 <b.eltzner@gmx.de>         #
# Octave/Matlab normxcorr2 implementation in python 3.5                                #
# Details:                                                                             #
# Normalized cross-correlation. Similiar results upto 3 significant digits.            #
# https://github.com/Sabrewarrior/normxcorr2-python/master/norxcorr2.py                #
# http://lordsabre.blogspot.ca/2017/09/matlab-normxcorr2-implemented-in-python.html    #
########################################################################################
from typing import Tuple, Any, Union
import numpy as np
from scipy.signal import fftconvolve


def normxcorr2(template, image, mode="full"):
    """
    Input arrays should be floating point numbers.
    :param template: N-D array, of template or filter you are using for cross-correlation.
    Must be less or equal dimensions to image.
    Length of each dimension must be less than length of image.
    :param image: N-D array
    :param mode: Options, "full", "valid", "same"
    full (Default): The output of fftconvolve is the full discrete linear convolution of the inputs. 
    Output size will be image size + 1/2 template size in each dimension.
    valid: The output consists only of those elements that do not rely on the zero-padding.
    same: The output is the same size as image, centered with respect to the ‘full’ output.
    :return: N-D array of same dimensions as image. Size depends on mode parameter.
    """

    # If this happens, it is probably a mistake
    if np.ndim(template) > np.ndim(image) or \
            len([i for i in range(np.ndim(template)) if template.shape[i] > image.shape[i]]) > 0:
        print("normxcorr2: TEMPLATE larger than IMG. Arguments may be swapped.")

    template = template - np.mean(template)
    image = image - np.mean(image)

    a1 = np.ones(template.shape)
    # Faster to flip up down and left right then use fftconvolve instead of scipy's correlate
    ar = np.flipud(np.fliplr(template))
    out = fftconvolve(image, ar.conj(), mode=mode)

    image = fftconvolve(np.square(image), a1, mode=mode) - \
            np.square(fftconvolve(image, a1, mode=mode)) / (np.prod(template.shape))

    # Remove small machine precision errors after subtraction
    image[np.where(image < 0)] = 0

    template = np.sum(np.square(template))
    out = out / np.sqrt(image * template)

    # Remove any divisions by 0 or very close to 0
    out[np.where(np.logical_not(np.isfinite(out)))] = 0

    return out


def extract_pattern(template, image, **kwargs) -> Tuple[np.ndarray, Tuple[int, int], Tuple[float, float]]:
    """
    extract_pattern: align the image to the template with normxcorr2
    :param template: The reference image
    :param image:
    :param kwargs:
    :return:
    >>> img_p, (r, c), (dr, dc) = extract_pattern(template, image)
    >>> # go down -dr, go right -dc to make image aligned to template.
    """
    if "PadSize" in kwargs:
        pad_size = kwargs['PadSize']
    else:
        pad_size = 5

    out = normxcorr2(template, image, mode="same")
    # xcorr2 最大值
    ind = np.argmax(out)
    # 换算成行列
    row, col = (ind // out.shape[1], ind % out.shape[1])
    temp_shape = template.shape
    im_shape = image.shape
    # 计算需要平移的量
    drow, dcol = row - (im_shape[0]-1)/2, col - (im_shape[1]-1)/2
    row_start, col_start, height, width = int(row - temp_shape[0] / 2), int(col - temp_shape[1] / 2), temp_shape[0], \
                                          temp_shape[1]
    inner_pattern = image[max(0, row_start - pad_size):min(row_start + height + pad_size, image.shape[0]),
                    max(0, col_start - pad_size):min(col_start + width + pad_size, image.shape[1])]
    return inner_pattern, (row, col), (drow, dcol)
