import matplotlib.pyplot as plt
import numpy as np
import scipy.io as sio
import scipy.optimize as sopt


def unbiased_var(x: np.ndarray, axis):
    x_mean = np.mean(x, axis=axis)
    return 1 / (x.shape[axis] - 1) * np.sum((x - x_mean) ** 2, axis=axis)


def __func(params, x, y):
    residual = (y - np.sum(unbiased_var(x / params, 0) * np.mean(x / params, 0)) / np.sum(
        np.mean(x / params, 0) ** 2)) ** 2
    return residual


def estimate_bm3d_para(data: np.ndarray, alp_bin_size: int, alp_th_fact: int, sig_bin_size: int, mask: np.ndarray) -> \
        tuple:
    """
    This function estimate alpha and sigma of an image.
    :param data: image to be estimated.
    :param alp_bin_size: Bin size for determining alpha.
    :param alp_th_fact: a factor to determine what threshold will be used for
                        determining alpha. For example, if AlpThFact is 1, all
                        data will be used. If AlpThFact is 2, only high 50% of
                        data will be used. If AlpThFact is 4, only high 25% of
                        data will be used.
    :param sig_bin_size: Bin size for determining sigma.
    :param mask: Target area.
    :return:
    """
    if data.shape[0] % 2:
        data = np.vstack((data, np.zeros((1, data.shape[1]))))
    if data.shape[1] % 2:
        data = np.hstack((data, np.zeros((data.shape[0], 1))))

    # Determine alpha
    bin_size = alp_bin_size
    dim1, dim2 = data.shape

    curr_sample_data = np.zeros((int(dim1 / bin_size), int(dim2 / bin_size)
                                 , bin_size ** 2))

    dim1ind = np.arange(0, dim1-1, bin_size)
    dim2ind = np.arange(0, dim2-1, bin_size)

    for i in range(bin_size):
        for j in range(bin_size):
            try:
                curr_sample_data[:, :, j + i * bin_size] = data[dim1ind + i, :][:, dim2ind + j]
            except Exception as e:
                print(j + i * bin_size)
                print(dim1ind + i)
                print(dim2ind + j)
                print(curr_sample_data.shape)
                print(data.shape)
    curr_mean_data = np.mean(curr_sample_data, 2)
    AT = sorted(curr_mean_data.flat, reverse=True)
    thresh = AT[np.round(len(AT) / alp_th_fact).astype(int) - 1]
    num_pxl = np.sum(curr_mean_data.flat > thresh)
    statsData = np.zeros((curr_sample_data.shape[2], num_pxl))

    curr_ind = 0
    for i in range(int(dim1 / bin_size)):
        for j in range(int(dim2 / bin_size)):
            if curr_mean_data[i, j] > thresh:
                statsData[:, curr_ind] = curr_sample_data[i, j, :]
                curr_ind = curr_ind + 1
    sio.savemat("statsData.mat", {'stats_data': statsData})
    # p = least_squares(__func, 1, args=(statsData, 1))
    p = sopt.leastsq(__func, 1, (statsData, 1))
    alpha = p[0][0]
    # p = sopt.minimize_scalar(__func, args=(statsData, 1))

    # determine sigma
    bin_size = sig_bin_size
    curr_sample_data = np.zeros((int(dim1 / bin_size), int(dim2 / bin_size), bin_size ** 2))
    dim1ind = np.arange(0, dim1, bin_size)
    dim2ind = np.arange(0, dim2, bin_size)
    for i in range(bin_size):
        for j in range(bin_size):
            curr_sample_data[:, :, j + i * bin_size] = data[dim1ind + i, :][:, dim2ind + j]
    binned_big_mask = np.zeros(mask.shape)

    for i in range(bin_size):
        for j in range(bin_size):
            binned_big_mask = binned_big_mask + np.roll(mask, (-i, -j), axis=(0, 1))
    binned_mask = binned_big_mask[np.arange(0, mask.shape[0], bin_size), :][:,
                  np.arange(0, mask.shape[1], bin_size)] / (bin_size ** 2)
    bg_masked = curr_sample_data * np.transpose(np.tile(binned_mask, [curr_sample_data.shape[2], 1, 1]), (1, 2, 0))
    bg_data = bg_masked[bg_masked != 0]
    curr_mean = np.mean(bg_data.flat)
    sample_var = unbiased_var(np.array(bg_data.flat), 0)
    meanalpha = alpha
    if sample_var <= curr_mean * meanalpha:
        sigma = 0
    else:
        sigma = np.sqrt(sample_var - curr_mean * meanalpha)

    return alpha, sigma
    # alpha, sigma
