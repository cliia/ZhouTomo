import os

import numpy as np
import bm3d
import scipy.io as sio
from scipy import interpolate

from .estimate_bm3d import estimate_bm3d_para
from .create_loose_mask import create_loose_mask


def easy_interp2(X, Y, V, xq):
    up_ind = 0
    down_ind = 0
    for i, x in enumerate(X):
        if x > xq:
            up_ind = i
            down_ind = i - 1
            break
    Vq = V[:, down_ind] + (V[:, up_ind] - V[:, down_ind]) / (X[up_ind] - X[down_ind]) * (xq - X[down_ind])
    return Vq


def anscombe_inverse_exact_unbiased(D: np.ndarray):
    file_path = os.path.abspath(__file__)
    project_path = os.path.dirname(file_path)
    data = sio.loadmat(project_path + "/Anscombe_vectors.mat")
    Efz = np.squeeze(data['Efz'])
    Ez = np.squeeze(data['Ez'])
    asymptotic = (D / 2) ** 2 - 1 / 8
    f = interpolate.interp1d(Efz, Ez, kind='linear', fill_value='extrapolate')
    exact_inverse = f(D)
    outside_exact_inverse_domain = D > max(Efz.flat)
    exact_inverse[outside_exact_inverse_domain] = asymptotic[outside_exact_inverse_domain]
    outside_exact_inverse_domain = D < (2 * np.sqrt(3 / 8))
    exact_inverse[outside_exact_inverse_domain] = 0

    return exact_inverse


def gen_anscombe_forward(z: np.ndarray, sigma, alpha, g):
    tmp = alpha * z + (3 / 8) * alpha ** 2 + sigma ** 2 - alpha * g
    tmp[tmp < 0] = 0
    fz = 2 / alpha * np.sqrt(tmp)
    return fz


def gen_anscombe_inverse_exact_unbiased(D, sigma, alpha, g):
    file_path = os.path.abspath(__file__)
    project_path = os.path.dirname(file_path)
    data = sio.loadmat(project_path + "/GenAnscombe_vectors.mat")
    Efzmatrix = data['Efzmatrix']
    Ez = np.squeeze(data['Ez'])
    sigmas = np.squeeze(data['sigmas'])

    sigma = sigma / alpha
    if sigma > np.max(sigmas):
        exact_inverse = anscombe_inverse_exact_unbiased(D) - sigma ** 2
        exact_inverse[exact_inverse < 0] = 0
        exact_inverse = exact_inverse
    elif sigma > 0:
        Efz = easy_interp2(sigmas, Ez, Efzmatrix, sigma)
        Efz = np.squeeze(Efz)
        f = interpolate.interp1d(Efz, Ez, kind='linear', fill_value='extrapolate')
        exact_inverse = f(D)
        outside_exact_inverse_domain = D > max(Efz.flat)
        asymptotic = anscombe_inverse_exact_unbiased(D) - sigma ** 2
        exact_inverse[outside_exact_inverse_domain] = asymptotic[outside_exact_inverse_domain]
        outside_exact_inverse_domain = D < min(Efz.flat)
        exact_inverse[outside_exact_inverse_domain] = 0
    elif sigma <= 0:
        exact_inverse = anscombe_inverse_exact_unbiased(D)
        print('[BM3D main WARNING] Got sigma <= 0.')
    else:
        raise ValueError("[BM3D main] sigma. Try to change the denoise strategy or corresponding kwargs.")
    return exact_inverse


def bm3d_main(image: np.ndarray, **kwargs):
    if "MinSize" in kwargs:
        min_size = kwargs["MinSize"]
    else:
        min_size = 1000
    if "DiskSize" in kwargs:
        disk_size = kwargs["DiskSize"]
    else:
        disk_size = 15

    if "Mask" in kwargs:
        mask = kwargs['Mask']
    else:
        # Create mask
        mask = create_loose_mask(image, MinSize=min_size, DiskSize=disk_size)

    alpha_bin_size = 2
    alpha_th_fact = 1
    sig_bin_size = 2
    alpha, sigma = estimate_bm3d_para(image, alpha_bin_size, alpha_th_fact, sig_bin_size, mask)
    # Do general Anscombe transform
    fz = gen_anscombe_forward(image, sigma, alpha, 0)

    # Rescale image
    scale_range = 0.7
    scale_shift = (1 - scale_range) / 2

    maxzans = np.max(fz.flat)
    minzans = np.min(fz.flat)
    fz = (fz - minzans) / (maxzans - minzans)
    curr_sigma_den = 0.96 / (maxzans - minzans)
    fz = fz * scale_range + scale_shift

    curr_sigma_den = curr_sigma_den * scale_range
    D = bm3d.bm3d(fz, curr_sigma_den, 'np')
    D = (D - scale_shift) / scale_range
    D = D * (maxzans - minzans) + minzans
    yhat0 = gen_anscombe_inverse_exact_unbiased(D, sigma, alpha, 0)
    yhat0 = yhat0 / alpha
    SF = np.sum((image * yhat0).flat) / np.sum(np.array(yhat0.flat) ** 2)
    image_denoised = yhat0 * SF
    return image_denoised
